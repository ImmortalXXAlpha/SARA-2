# local_ai.py
import torch
import gc
import threading
import time
from typing import Optional, Callable, Dict

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig
)

class LocalAI:
    """
    Local AI backend supporting:
    - multiple models (registry)
    - auto VRAM detection & auto model selection
    - tokenizer caching
    - 4-bit quantization when using GPU (BitsAndBytesConfig)
    - progress/status callbacks for UI integration
    - benchmark (tokens/sec) after load
    - idle auto-unload
    - GPU/CPU override and VRAM budget enforcement
    """

    AVAILABLE_MODELS = {
        # Keys are short names user/GUI can show. Values are HF model ids or local paths.
        "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
        "phi3-mini": "microsoft/Phi-3.5-mini-instruct",
        "deepseek-1.5b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "qwen2.5-1.5b": "Qwen/Qwen2.5-1.5B-Instruct"
    }

    # Estimated VRAM requirements (GB) for smart selection; approximate and conservative
    MODEL_VRAM_REQ_GB = {
        "mistral-7b": 6.0,     # quantized 4bit ~ 5-7GB depending on offload
        "phi3-mini": 3.0,
        "deepseek-1.5b": 2.0,
        "qwen2.5-1.5b": 1.5
    }

    def __init__(self,
                 model_key: str = "phi3-mini",
                 force_cpu: bool = False,
                 vram_limit_gb: Optional[float] = None,
                 idle_unload_seconds: int = 600):
        # model selection / caching
        if model_key not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model key: {model_key}")
        self.model_key = model_key
        self.model_name = self.AVAILABLE_MODELS[model_key]

        # runtime objects
        self.model = None
        self.tokenizer = None

        # cache tokenizers to speed switching
        self._tokenizer_cache: Dict[str, AutoTokenizer] = {}

        # device / policy flags
        self.force_cpu = force_cpu
        self.vram_limit_gb = vram_limit_gb  # if set, choose model that fits under this limit
        self.idle_unload_seconds = idle_unload_seconds

        # state flags
        self.is_loading = False
        self.is_loaded = False
        self._idle_timer: Optional[threading.Timer] = None

        # callbacks (UI should assign callables)
        self.progress_callback: Optional[Callable[[int], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        self.loaded_callback: Optional[Callable[[], None]] = None
        self.vram_callback: Optional[Callable[[float, float], None]] = None  # (used, total) in GB
        self.benchmark_callback: Optional[Callable[[float], None]] = None  # tokens/sec

    # -----------------------
    # Helper: emit callbacks
    # -----------------------
    def _emit_progress(self, percent: int):
        if callable(self.progress_callback):
            try:
                self.progress_callback(int(max(0, min(100, percent))))
            except Exception:
                pass

    def _emit_status(self, msg: str):
        if callable(self.status_callback):
            try:
                self.status_callback(str(msg))
            except Exception:
                pass

    def _emit_loaded(self):
        if callable(self.loaded_callback):
            try:
                self.loaded_callback()
            except Exception:
                pass

    def _emit_vram(self):
        if not torch.cuda.is_available():
            if callable(self.vram_callback):
                try:
                    self.vram_callback(0.0, 0.0)
                except Exception:
                    pass
            return
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if callable(self.vram_callback):
                try:
                    self.vram_callback(round(used, 3), round(total, 3))
                except Exception:
                    pass
        except Exception:
            pass

    def _emit_benchmark(self, tps: float):
        if callable(self.benchmark_callback):
            try:
                self.benchmark_callback(float(tps))
            except Exception:
                pass

    # -----------------------
    # VRAM detection & model selection
    # -----------------------
    def detect_vram_gb(self) -> float:
        """Return total VRAM in GB (0.0 if no CUDA)."""
        if not torch.cuda.is_available() or self.force_cpu:
            return 0.0
        props = torch.cuda.get_device_properties(0)
        return round(props.total_memory / (1024 ** 3), 2)

    def auto_select_model_key(self) -> str:
        """Choose the best model key given detected VRAM and optional vram_limit_gb."""
        vram = self.detect_vram_gb()
        limit = self.vram_limit_gb or vram
        # sort by descending capability
        candidates = sorted(self.MODEL_VRAM_REQ_GB.items(), key=lambda x: -x[1])
        for key, req in candidates:
            if req <= limit:
                return key
        # fallback to smallest
        return min(self.MODEL_VRAM_REQ_GB, key=self.MODEL_VRAM_REQ_GB.get)

    # -----------------------
    # Unload model (cleanup)
    # -----------------------
    def unload_model(self):
        self._emit_status("Unloading model and freeing memory...")
        self._emit_progress(5)
        try:
            if self.model is not None:
                del self.model
            if self.tokenizer is not None:
                # keep tokenizer in cache optionally
                # do NOT delete from cache so reloading same model may be faster
                # del self.tokenizer
                pass
            gc_collected = False
            try:
                gc_collected = True
                import gc
                gc.collect()
            except Exception:
                pass
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                    # ipc_collect may not exist on some torch builds; guard it
                    if hasattr(torch.cuda, "ipc_collect"):
                        torch.cuda.ipc_collect()
                except Exception:
                    pass
        except Exception as e:
            self._emit_status(f"Warning during unload: {e}")
        finally:
            self.model = None
            # Note: we keep tokenizer cached for faster switch by default
            self.is_loaded = False
            self._emit_progress(15)

    # -----------------------
    # Tokenizer loader (UI thread will call via ModelLoaderThread)
    # -----------------------
    def _load_tokenizer(self):
        """
        Load tokenizer (returns tokenizer object). May be called from ModelLoaderThread.
        Uses tokenizer cache to speed up repeated switches.
        """
        self._emit_status("Loading tokenizer...")
        self._emit_progress(30)

        # If cached -> reuse
        if self.model_name in self._tokenizer_cache:
            tok = self._tokenizer_cache[self.model_name]
            self._emit_progress(40)
            return tok

        tok = AutoTokenizer.from_pretrained(self.model_name, use_fast=True, trust_remote_code=True)
        self._tokenizer_cache[self.model_name] = tok
        self._emit_progress(40)
        return tok

    # -----------------------
    # Model loader (UI thread will call via ModelLoaderThread)
    # -----------------------
    def _load_model(self):
        """
        Load model weights. Returns model object.
        This method uses BitsAndBytesConfig for 4-bit quantization when GPU is used.
        """
        self._emit_status("Loading model weights...")
        self._emit_progress(55)

        use_gpu = (torch.cuda.is_available() and not self.force_cpu)
        if use_gpu:
            # Quantization config for GPU
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                quantization_config=quant_cfg,
                trust_remote_code=True
            )
        else:
            # CPU fallback: do not use quantization config (bitsandbytes expects GPU)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="cpu",
                trust_remote_code=True
            )

        self._emit_progress(80)
        self._emit_status("Finalizing model setup...")
        # small delay to let caches settle (helps progress UX)
        time.sleep(0.5)
        return model

    # -----------------------
    # Public: start load (convenience)
    # -----------------------
    def start_load(self):
        """
        Convenience: starts background thread that will call the tokenizer/model load steps sequentially
        and emit progress/status updates. UI can instead call _load_tokenizer/_load_model individually
        (e.g. from ModelLoaderThread) — both approaches supported.
        """
        if self.is_loading or self.is_loaded:
            return
        self.is_loading = True

        def _do_load():
            try:
                self._emit_progress(10)
                self._emit_status("Beginning load...")
                self._emit_progress(20)
                # Unload existing first
                self.unload_model()
                # tokenizer
                tok = self._load_tokenizer()
                self.tokenizer = tok
                # model
                mdl = self._load_model()
                self.model = mdl
                self.is_loaded = True
                self.is_loading = False
                self._emit_progress(100)
                self._emit_status("Model ready")
                # benchmark (in background thread so UI doesn't block)
                try:
                    tps = self._benchmark_tokens_per_second()
                    self._emit_benchmark(tps)
                except Exception:
                    pass
                self._emit_loaded()
                # start idle timer
                self._start_idle_timer()
            except Exception as e:
                self._emit_status(f"Load failed: {e}")
                self.is_loading = False

        t = threading.Thread(target=_do_load, daemon=True)
        t.start()

    # -----------------------
    # Generation
    # -----------------------
    def generate(self, prompt: str, max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        """Synchronous generate call. Should be run from a worker thread in the UI."""
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return "⚠️ Model not ready."

        # reset idle timer on activity
        self._reset_idle_timer()

        try:
            formatted = f"[INST] {prompt} [/INST]"
            inputs = self.tokenizer(formatted, return_tensors="pt")
            # move inputs to model device (if model parameters are on cuda, send inputs to their device)
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                out = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            text = self.tokenizer.decode(out[0], skip_special_tokens=True)
            return text.replace(formatted, "").strip()
        except Exception as e:
            return f"❌ Generation error: {e}"

    # -----------------------
    # Benchmark
    # -----------------------
    def _benchmark_tokens_per_second(self, test_prompt: str = "Hello", new_tokens: int = 16) -> float:
        """Run a short generation to estimate tokens/sec. Returns tps float."""
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return 0.0
        try:
            # prepare
            inputs = self.tokenizer(test_prompt, return_tensors="pt")
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            t0 = time.time()
            _ = self.model.generate(**inputs, max_new_tokens=new_tokens)
            t1 = time.time()
            secs = max(1e-6, (t1 - t0))
            tps = new_tokens / secs
            return round(tps, 2)
        except Exception:
            return 0.0

    # -----------------------
    # VRAM usage helper (UI can poll periodically)
    # -----------------------
    def get_vram_usage_gb(self) -> (float, float):
        """Return (used_gb, total_gb)"""
        if not torch.cuda.is_available() or self.force_cpu:
            return (0.0, 0.0)
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return (round(used, 3), round(total, 3))
        except Exception:
            return (0.0, 0.0)

    # -----------------------
    # Model switching (public)
    # -----------------------
    def switch_model(self, new_key: str):
        """
        Switch model: updates keys, unloads, and kicks off a load using start_load().
        """
        if new_key not in self.AVAILABLE_MODELS:
            return f"Unknown model: {new_key}"
        self._emit_status(f"Switching to {new_key}...")
        self._emit_progress(1)
        self.model_key = new_key
        self.model_name = self.AVAILABLE_MODELS[new_key]
        # unload then start background load
        self.unload_model()
        self.start_load()
        return f"Loading {new_key}..."

    # -----------------------
    # Settings: force CPU / VRAM limit
    # -----------------------
    def set_force_cpu(self, flag: bool):
        self.force_cpu = bool(flag)

    def set_vram_limit(self, gb: Optional[float]):
        """
        Set a VRAM budget (GB). If None, no extra limit beyond actual GPU VRAM.
        """
        if gb is None or gb <= 0:
            self.vram_limit_gb = None
        else:
            self.vram_limit_gb = float(gb)

    # -----------------------
    # Idle unload timer
    # -----------------------
    def _start_idle_timer(self):
        self._cancel_idle_timer()
        if not self.idle_unload_seconds or self.idle_unload_seconds <= 0:
            return
        self._idle_timer = threading.Timer(self.idle_unload_seconds, self._idle_unload)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _reset_idle_timer(self):
        self._start_idle_timer()

    def _cancel_idle_timer(self):
        try:
            if self._idle_timer and isinstance(self._idle_timer, threading.Timer):
                self._idle_timer.cancel()
        except Exception:
            pass
        self._idle_timer = None

    def _idle_unload(self):
        """
        Called when idle timeout expires.
        """
        try:
            self._emit_status("Idle timeout reached — unloading model to save RAM.")
            self.unload_model()
        except Exception:
            pass

    # -----------------------
    # Shutdown helper
    # -----------------------
    def shutdown(self):
        """
        Call this when your app is closing to ensure GPU memory is freed.
        """
        self._cancel_idle_timer()
        self.unload_model()
