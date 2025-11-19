# ai/nova_ai.py
"""
NovaAI - central AI manager for SARA
Features:
 - Multi-model registry + auto-selection by VRAM
 - 4-bit quantization via BitsAndBytesConfig (if GPU available)
 - Async load/unload, GC and CUDA cleanup
 - Callbacks for progress, status, benchmark, vram updates
 - Model switching, force-CPU, VRAM budget
"""

import torch
import time
import threading
import gc
from typing import Optional, Callable, Dict

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig
)

class NovaAI:
    # Available model keys -> HF ids (you can add local paths)
    MODELS = {
        "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
        "phi3-mini": "microsoft/Phi-3.5-mini-instruct",
        "deepseek-1.5b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "qwen2.5-1.5b": "Qwen/Qwen2.5-1.5B-Instruct"
    }

    # Rough VRAM requirement estimates in GB (quantized)
    VRAM_REQ_GB = {
        "mistral-7b": 6.0,
        "phi3-mini": 3.0,
        "deepseek-1.5b": 2.0,
        "qwen2.5-1.5b": 1.5
    }

    def __init__(self,
                 model_key: str = "phi3-mini",
                 force_cpu: bool = False,
                 vram_limit_gb: Optional[float] = None,
                 idle_unload_seconds: int = 600):
        if model_key not in self.MODELS:
            raise ValueError("Unknown model key")
        self.model_key = model_key
        self.model_name = self.MODELS[model_key]

        self.force_cpu = force_cpu
        self.vram_limit_gb = vram_limit_gb
        self.idle_unload_seconds = idle_unload_seconds

        self.model = None
        self.tokenizer = None
        self._tokenizer_cache: Dict[str, AutoTokenizer] = {}

        self.is_loaded = False
        self.is_loading = False

        self._idle_timer = None

        # Callbacks (UI should set these)
        self.on_progress: Optional[Callable[[int], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_loaded: Optional[Callable[[], None]] = None
        self.on_benchmark: Optional[Callable[[float], None]] = None
        self.on_vram: Optional[Callable[[float, float], None]] = None

        # internal lock
        self._lock = threading.RLock()

    # ----------------- utility emits -----------------
    def _emit_progress(self, v: int):
        cb = self.on_progress
        if cb:
            try: cb(int(max(0, min(100, v))))
            except Exception: pass

    def _emit_status(self, s: str):
        cb = self.on_status
        if cb:
            try: cb(str(s))
            except Exception: pass

    def _emit_loaded(self):
        if self.on_loaded:
            try: self.on_loaded()
            except Exception: pass

    def _emit_benchmark(self, tps: float):
        if self.on_benchmark:
            try: self.on_benchmark(float(tps))
            except Exception: pass

    def _emit_vram(self):
        if not torch.cuda.is_available() or self.force_cpu:
            if self.on_vram:
                try: self.on_vram(0.0, 0.0)
                except Exception: pass
            return
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if self.on_vram:
                try: self.on_vram(round(used,3), round(total,3))
                except Exception: pass
        except Exception:
            pass

    # ----------------- VRAM helpers -----------------
    def detect_vram_gb(self) -> float:
        if not torch.cuda.is_available() or self.force_cpu:
            return 0.0
        props = torch.cuda.get_device_properties(0)
        return round(props.total_memory / (1024**3), 2)

    def auto_select_model_key(self) -> str:
        total_vram = self.detect_vram_gb()
        limit = self.vram_limit_gb if self.vram_limit_gb else total_vram
        # pick largest model that fits under limit
        sorted_models = sorted(self.VRAM_REQ_GB.items(), key=lambda x: -x[1])
        for key, req in sorted_models:
            if req <= (limit or 0):
                return key
        # fallback smallest
        return min(self.VRAM_REQ_GB, key=self.VRAM_REQ_GB.get)

    def get_vram_usage_gb(self):
        """Return (used_gb, total_gb) tuple"""
        if not torch.cuda.is_available() or self.force_cpu:
            return (0.0, 0.0)
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return (round(used, 3), round(total, 3))
        except Exception:
            return (0.0, 0.0)

    # ----------------- load/unload -----------------
    def unload(self):
        with self._lock:
            self._emit_status("Unloading model and freeing memory...")
            self._emit_progress(5)
            try:
                if self.model is not None:
                    del self.model
                # keep tokenizer cached to speed reloads
                gc.collect()
                if torch.cuda.is_available():
                    try:
                        torch.cuda.empty_cache()
                        if hasattr(torch.cuda, "ipc_collect"):
                            torch.cuda.ipc_collect()
                    except Exception:
                        pass
            except Exception as e:
                self._emit_status(f"Unload warning: {e}")
            finally:
                self.model = None
                self.is_loaded = False
                self._emit_progress(15)

    def _load_tokenizer(self):
        self._emit_status("Loading tokenizer...")
        self._emit_progress(30)
        if self.model_name in self._tokenizer_cache:
            tok = self._tokenizer_cache[self.model_name]
            self._emit_progress(40)
            return tok
        tok = AutoTokenizer.from_pretrained(self.model_name, use_fast=True, trust_remote_code=True)
        self._tokenizer_cache[self.model_name] = tok
        self._emit_progress(40)
        return tok

    def _load_model_weights(self):
        self._emit_status("Loading model weights...")
        self._emit_progress(55)
        use_gpu = torch.cuda.is_available() and not self.force_cpu
        if use_gpu:
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )
            mdl = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                quantization_config=quant_cfg,
                trust_remote_code=True
            )
        else:
            mdl = AutoModelForCausalLM.from_pretrained(self.model_name, device_map="cpu", trust_remote_code=True)
        self._emit_progress(80)
        self._emit_status("Finalizing model setup...")
        time.sleep(0.4)
        return mdl

    def start_load(self):
        with self._lock:
            if self.is_loaded or self.is_loading:
                return
            self.is_loading = True

        def _target():
            try:
                self._emit_progress(10)
                self._emit_status("Beginning model load...")
                # Unload first
                self.unload()
                # Tokenizer
                self.tokenizer = self._load_tokenizer()
                # Model
                self.model = self._load_model_weights()
                self.is_loaded = True
                self.is_loading = False
                self._emit_progress(100)
                self._emit_status("Model ready")
                # benchmark asynchronously
                try:
                    tps = self._benchmark_tps()
                    self._emit_benchmark(tps)
                except Exception:
                    pass
                self._emit_loaded()
                self._emit_vram()
                self._start_idle_timer()
            except Exception as e:
                self.is_loading = False
                self._emit_status(f"Load failed: {e}")

        t = threading.Thread(target=_target, daemon=True)
        t.start()

    # ----------------- generate -----------------
    def generate(self, prompt: str, max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        if not self.is_loaded or self.model is None:
            return "⚠️ Model not ready."
        # reset idle timer
        self._reset_idle_timer()
        try:
            formatted = f"[INST] {prompt} [/INST]"
            inputs = self.tokenizer(formatted, return_tensors="pt")
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
            txt = self.tokenizer.decode(out[0], skip_special_tokens=True)
            return txt.replace(formatted, "").strip()
        except Exception as e:
            return f"❌ Generation error: {e}"

    # ----------------- benchmark -----------------
    def _benchmark_tps(self, test_prompt: str = "Hello", new_tokens: int = 16) -> float:
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return 0.0
        try:
            inputs = self.tokenizer(test_prompt, return_tensors="pt")
            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            st = time.time()
            _ = self.model.generate(**inputs, max_new_tokens=new_tokens)
            en = time.time()
            secs = max(1e-6, (en - st))
            tps = new_tokens / secs
            return round(tps, 2)
        except Exception:
            return 0.0

    # ----------------- model switch & settings -----------------
    def switch_model(self, new_key: str):
        if new_key not in self.MODELS:
            return f"Unknown model {new_key}"
        self._emit_status(f"Switching to {new_key}...")
        self._emit_progress(2)
        self.model_key = new_key
        self.model_name = self.MODELS[new_key]
        self.unload()
        self.start_load()
        return f"Loading {new_key}"

    def set_force_cpu(self, flag: bool):
        self.force_cpu = bool(flag)

    def set_vram_limit(self, gb: Optional[float]):
        self.vram_limit_gb = None if (gb is None or gb <= 0) else float(gb)

    # ----------------- idle unload -----------------
    def _start_idle_timer(self):
        self._cancel_idle_timer()
        if not self.idle_unload_seconds or self.idle_unload_seconds <= 0:
            return
        t = threading.Timer(self.idle_unload_seconds, self._idle_unload)
        t.daemon = True
        t.start()
        self._idle_timer = t

    def _reset_idle_timer(self):
        self._start_idle_timer()

    def _cancel_idle_timer(self):
        try:
            if self._idle_timer:
                self._idle_timer.cancel()
        except Exception:
            pass
        self._idle_timer = None

    def _idle_unload(self):
        try:
            self._emit_status("Idle timeout — unloading model to free VRAM.")
            self.unload()
        except Exception:
            pass

    def shutdown(self):
        self._cancel_idle_timer()
        self.unload()