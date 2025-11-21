# ai/nova_ai.py
"""
NovaAI - Simplified and robust version
Avoids complex threading during model operations.
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
    MODELS = {
        "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
        "phi3-mini": "microsoft/Phi-3.5-mini-instruct",
        "deepseek-1.5b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        "qwen2.5-1.5b": "Qwen/Qwen2.5-1.5B-Instruct"
    }

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
            model_key = "phi3-mini"
        self.model_key = model_key
        self.model_name = self.MODELS[model_key]

        self.force_cpu = force_cpu
        self.vram_limit_gb = vram_limit_gb
        self.idle_unload_seconds = idle_unload_seconds

        self.model = None
        self.tokenizer = None
        self._tokenizer_cache: Dict[str, AutoTokenizer] = {}
        self._device = "cpu"

        self.is_loaded = False
        self.is_loading = False
        self._idle_timer = None
        self._load_thread = None

        # Callbacks
        self.on_progress: Optional[Callable[[int], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_loaded: Optional[Callable[[], None]] = None
        self.on_benchmark: Optional[Callable[[float], None]] = None
        self.on_vram: Optional[Callable[[float, float], None]] = None

    # ---- Callbacks ----
    def _emit_progress(self, v):
        if self.on_progress:
            try:
                self.on_progress(int(max(0, min(100, v))))
            except:
                pass

    def _emit_status(self, s):
        if self.on_status:
            try:
                self.on_status(str(s))
            except:
                pass

    def _emit_loaded(self):
        if self.on_loaded:
            try:
                self.on_loaded()
            except:
                pass

    def _emit_benchmark(self, t):
        if self.on_benchmark:
            try:
                self.on_benchmark(float(t))
            except:
                pass

    def _emit_vram(self):
        if self.on_vram:
            try:
                used, total = self.get_vram_usage_gb()
                self.on_vram(used, total)
            except:
                pass

    # ---- VRAM ----
    def detect_vram_gb(self) -> float:
        try:
            if not torch.cuda.is_available() or self.force_cpu:
                return 0.0
            return round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
        except:
            return 0.0

    def get_vram_usage_gb(self):
        try:
            if not torch.cuda.is_available() or self.force_cpu:
                return (0.0, 0.0)
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return (round(used, 3), round(total, 3))
        except:
            return (0.0, 0.0)

    def auto_select_model_key(self) -> str:
        limit = self.vram_limit_gb or self.detect_vram_gb()
        for key, req in sorted(self.VRAM_REQ_GB.items(), key=lambda x: -x[1]):
            if req <= (limit or 0):
                return key
        return "qwen2.5-1.5b"

    # ---- Unload ----
    def unload(self):
        """Unload model and free memory."""
        self._emit_status("Unloading model...")
        self.is_loaded = False
        
        # Clear model
        if self.model is not None:
            try:
                # Move to CPU first if on GPU (helps with cleanup)
                if hasattr(self.model, 'cpu'):
                    try:
                        self.model.cpu()
                    except:
                        pass
                del self.model
            except:
                pass
            self.model = None
        
        # DON'T clear tokenizer - keep it cached
        
        # Force garbage collection
        gc.collect()
        
        # Clear CUDA cache
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except:
                pass
        
        self._emit_status("Unloaded")

    # ---- Load ----
    def _do_load(self):
        """Internal load method - runs in thread."""
        try:
            self.is_loading = True
            self._emit_progress(10)
            self._emit_status("Preparing to load...")
            
            # Unload any existing model first
            if self.model is not None:
                self.unload()
            
            # Wait a moment for memory to clear
            time.sleep(0.5)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Load tokenizer
            self._emit_status("Loading tokenizer...")
            self._emit_progress(25)
            
            if self.model_name in self._tokenizer_cache:
                self.tokenizer = self._tokenizer_cache[self.model_name]
            else:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    use_fast=True,
                    trust_remote_code=True
                )
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                self._tokenizer_cache[self.model_name] = self.tokenizer
            
            self._emit_progress(40)
            
            # Load model
            self._emit_status("Loading model (this may take a minute)...")
            self._emit_progress(50)
            
            use_gpu = torch.cuda.is_available() and not self.force_cpu
            
            if use_gpu:
                try:
                    quant_cfg = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16
                    )
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        device_map="auto",
                        quantization_config=quant_cfg,
                        trust_remote_code=True
                    )
                    self._device = "cuda"
                except Exception as e:
                    # Fallback to CPU if GPU fails
                    self._emit_status(f"GPU failed ({e}), trying CPU...")
                    gc.collect()
                    torch.cuda.empty_cache()
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_name,
                        device_map="cpu",
                        trust_remote_code=True
                    )
                    self._device = "cpu"
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    device_map="cpu",
                    trust_remote_code=True
                )
                self._device = "cpu"
            
            self._emit_progress(90)
            self._emit_status("Finalizing...")
            
            self.is_loaded = True
            self.is_loading = False
            
            self._emit_progress(100)
            self._emit_status("Ready")
            
            # Quick benchmark
            try:
                tps = self._benchmark_tps()
                self._emit_benchmark(tps)
            except:
                pass
            
            self._emit_vram()
            self._emit_loaded()
            self._start_idle_timer()
            
        except Exception as e:
            self._emit_status(f"Load failed: {e}")
            self.is_loading = False
            self.is_loaded = False

    def start_load(self):
        """Start loading model in background."""
        if self.is_loading:
            return
        
        # Wait for any previous load thread to finish
        if self._load_thread is not None and self._load_thread.is_alive():
            return
        
        self._load_thread = threading.Thread(target=self._do_load, daemon=True)
        self._load_thread.start()

    # ---- Switch model ----
    def switch_model(self, new_key: str):
        """Switch to different model."""
        if new_key not in self.MODELS:
            return f"Unknown model: {new_key}"
        
        if self.is_loading:
            return "Already loading, please wait..."
        
        if new_key == self.model_key and self.is_loaded:
            return f"Already using {new_key}"
        
        # Update model info
        self.model_key = new_key
        self.model_name = self.MODELS[new_key]
        
        self._emit_status(f"Switching to {new_key}...")
        self._emit_progress(5)
        
        # Unload current model synchronously
        self.unload()
        
        # Wait for memory cleanup
        time.sleep(0.3)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Start loading new model
        self.start_load()
        
        return f"Loading {new_key}..."

    # ---- Generate ----
    def generate(self, prompt: str, max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return "⚠️ Model not ready."
        
        if self.is_loading:
            return "⚠️ Model is loading..."
        
        self._reset_idle_timer()

        try:
            formatted = f"[INST] {prompt} [/INST]"
            
            inputs = self.tokenizer(
                formatted,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            )
            
            # Move to device
            if self._device == "cuda" and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                "do_sample": temperature > 0,
            }
            
            if temperature > 0:
                gen_kwargs["temperature"] = temperature
                gen_kwargs["top_p"] = 0.9

            with torch.no_grad():
                outputs = self.model.generate(**inputs, **gen_kwargs)
            
            # Decode only new tokens
            input_len = inputs["input_ids"].shape[1]
            new_tokens = outputs[0][input_len:]
            response = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            return f"❌ Error: {e}"

    # ---- Benchmark ----
    def _benchmark_tps(self) -> float:
        try:
            if not self.is_loaded or self.model is None:
                return 0.0
            
            inputs = self.tokenizer("Hello", return_tensors="pt")
            if self._device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            n_tokens = 16
            t0 = time.perf_counter()
            with torch.no_grad():
                self.model.generate(**inputs, max_new_tokens=n_tokens, do_sample=False)
            t1 = time.perf_counter()
            
            return round(n_tokens / max(0.01, t1 - t0), 2)
        except:
            return 0.0

    # ---- Settings ----
    def set_force_cpu(self, flag: bool):
        self.force_cpu = bool(flag)

    def set_vram_limit(self, gb: Optional[float]):
        self.vram_limit_gb = None if (gb is None or gb <= 0) else float(gb)

    # ---- Idle timer ----
    def _start_idle_timer(self):
        self._cancel_idle_timer()
        if self.idle_unload_seconds and self.idle_unload_seconds > 0:
            self._idle_timer = threading.Timer(self.idle_unload_seconds, self._on_idle)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _reset_idle_timer(self):
        self._start_idle_timer()

    def _cancel_idle_timer(self):
        if self._idle_timer:
            try:
                self._idle_timer.cancel()
            except:
                pass
            self._idle_timer = None

    def _on_idle(self):
        self._emit_status("Idle - unloading model")
        self.unload()

    def shutdown(self):
        self._cancel_idle_timer()
        self.unload()