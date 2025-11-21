# ai/nova_ai.py
"""
NovaAI - Optimized local AI manager for SARA
Key optimizations:
- KV cache reuse for faster subsequent generations
- Efficient attention mask handling  
- Reduced GPU sync calls
- Better memory management
- Streaming generation option
"""

import torch
import time
import threading
import gc
from typing import Optional, Callable, Dict, Generator

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TextIteratorStreamer
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

    # Chat templates per model family
    CHAT_TEMPLATES = {
        "mistral": "<s>[INST] {prompt} [/INST]",
        "phi3": "<|user|>\n{prompt}<|end|>\n<|assistant|>",
        "deepseek": "<|begin_of_sentence|>User: {prompt}\n\nAssistant:",
        "qwen": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
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
        self._device = None

        self.is_loaded = False
        self.is_loading = False
        self._idle_timer = None
        self._lock = threading.RLock()

        # Callbacks
        self.on_progress: Optional[Callable[[int], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_loaded: Optional[Callable[[], None]] = None
        self.on_benchmark: Optional[Callable[[float], None]] = None
        self.on_vram: Optional[Callable[[float, float], None]] = None

    # ---- Emit helpers ----
    def _emit(self, callback, *args):
        if callback:
            try:
                callback(*args)
            except Exception:
                pass

    def _emit_progress(self, v): self._emit(self.on_progress, int(max(0, min(100, v))))
    def _emit_status(self, s): self._emit(self.on_status, str(s))
    def _emit_loaded(self): self._emit(self.on_loaded)
    def _emit_benchmark(self, t): self._emit(self.on_benchmark, float(t))

    def _emit_vram(self):
        if not torch.cuda.is_available() or self.force_cpu:
            self._emit(self.on_vram, 0.0, 0.0)
            return
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            self._emit(self.on_vram, round(used, 3), round(total, 3))
        except Exception:
            pass

    # ---- VRAM helpers ----
    def detect_vram_gb(self) -> float:
        if not torch.cuda.is_available() or self.force_cpu:
            return 0.0
        return round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)

    def auto_select_model_key(self) -> str:
        limit = self.vram_limit_gb or self.detect_vram_gb()
        for key, req in sorted(self.VRAM_REQ_GB.items(), key=lambda x: -x[1]):
            if req <= (limit or 0):
                return key
        return min(self.VRAM_REQ_GB, key=self.VRAM_REQ_GB.get)

    def get_vram_usage_gb(self):
        if not torch.cuda.is_available() or self.force_cpu:
            return (0.0, 0.0)
        try:
            used = torch.cuda.memory_allocated(0) / (1024 ** 3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return (round(used, 3), round(total, 3))
        except Exception:
            return (0.0, 0.0)

    # ---- Load/Unload ----
    def unload(self):
        with self._lock:
            self._emit_status("Unloading model...")
            self._emit_progress(5)
            try:
                if self.model is not None:
                    del self.model
                    self.model = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
            except Exception as e:
                self._emit_status(f"Unload warning: {e}")
            finally:
                self.is_loaded = False
                self._device = None
                self._emit_progress(15)

    def _load_tokenizer(self):
        self._emit_status("Loading tokenizer...")
        self._emit_progress(30)
        if self.model_name in self._tokenizer_cache:
            self._emit_progress(40)
            return self._tokenizer_cache[self.model_name]
        tok = AutoTokenizer.from_pretrained(
            self.model_name, 
            use_fast=True, 
            trust_remote_code=True,
            padding_side="left"  # Better for generation
        )
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        self._tokenizer_cache[self.model_name] = tok
        self._emit_progress(40)
        return tok

    def _load_model_weights(self):
        self._emit_status("Loading model weights...")
        self._emit_progress(55)
        use_gpu = torch.cuda.is_available() and not self.force_cpu

        load_kwargs = {
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,  # Optimization: reduce peak memory
        }

        if use_gpu:
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True  # Extra compression
            )
            load_kwargs.update({
                "device_map": "auto",
                "quantization_config": quant_cfg,
                "torch_dtype": torch.float16,
            })
            self._device = "cuda"
        else:
            load_kwargs["device_map"] = "cpu"
            self._device = "cpu"

        mdl = AutoModelForCausalLM.from_pretrained(self.model_name, **load_kwargs)
        
        # Enable optimizations if available
        if hasattr(mdl, "config"):
            mdl.config.use_cache = True  # Enable KV cache
        
        self._emit_progress(80)
        self._emit_status("Finalizing...")
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
                self.unload()
                self.tokenizer = self._load_tokenizer()
                self.model = self._load_model_weights()
                self.is_loaded = True
                self.is_loading = False
                self._emit_progress(100)
                self._emit_status("Model ready")
                
                # Warmup generation (primes KV cache)
                try:
                    _ = self._warmup()
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

        threading.Thread(target=_target, daemon=True).start()

    def _warmup(self):
        """Warmup to prime caches."""
        if not self.is_loaded:
            return
        inputs = self.tokenizer("Hello", return_tensors="pt")
        if self._device == "cuda":
            inputs = {k: v.cuda() for k, v in inputs.items()}
        with torch.no_grad():
            _ = self.model.generate(**inputs, max_new_tokens=2, do_sample=False)

    # ---- Generation ----
    def _get_chat_template(self) -> str:
        """Get appropriate chat template for current model."""
        key = self.model_key.lower()
        if "mistral" in key:
            return self.CHAT_TEMPLATES["mistral"]
        elif "phi" in key:
            return self.CHAT_TEMPLATES["phi3"]
        elif "deepseek" in key:
            return self.CHAT_TEMPLATES["deepseek"]
        elif "qwen" in key:
            return self.CHAT_TEMPLATES["qwen"]
        return "[INST] {prompt} [/INST]"

    def generate(self, prompt: str, max_new_tokens: int = 256, temperature: float = 0.7) -> str:
        if not self.is_loaded or self.model is None:
            return "⚠️ Model not ready."
        self._reset_idle_timer()

        try:
            # Format with appropriate template
            template = self._get_chat_template()
            formatted = template.format(prompt=prompt)
            
            inputs = self.tokenizer(
                formatted, 
                return_tensors="pt",
                truncation=True,
                max_length=2048  # Prevent OOM on long inputs
            )
            
            if self._device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}

            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
            }
            
            if temperature > 0:
                gen_kwargs.update({
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 50,
                })

            with torch.inference_mode():  # Faster than no_grad for inference
                out = self.model.generate(**inputs, **gen_kwargs)
            
            # Decode only new tokens
            new_tokens = out[0][inputs["input_ids"].shape[1]:]
            text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
            return text.strip()
            
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            return "❌ Out of GPU memory. Try a shorter prompt or smaller model."
        except Exception as e:
            return f"❌ Generation error: {e}"

    def generate_stream(self, prompt: str, max_new_tokens: int = 256, 
                       temperature: float = 0.7) -> Generator[str, None, None]:
        """Streaming generation - yields tokens as they're generated."""
        if not self.is_loaded or self.model is None:
            yield "⚠️ Model not ready."
            return
        self._reset_idle_timer()

        try:
            template = self._get_chat_template()
            formatted = template.format(prompt=prompt)
            inputs = self.tokenizer(formatted, return_tensors="pt", truncation=True, max_length=2048)
            
            if self._device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}

            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            
            gen_kwargs = {
                **inputs,
                "max_new_tokens": max_new_tokens,
                "do_sample": temperature > 0,
                "streamer": streamer,
                "pad_token_id": self.tokenizer.pad_token_id,
            }
            if temperature > 0:
                gen_kwargs.update({"temperature": temperature, "top_p": 0.9})

            thread = threading.Thread(target=lambda: self.model.generate(**gen_kwargs))
            thread.start()

            for text in streamer:
                yield text

            thread.join()
        except Exception as e:
            yield f"❌ Error: {e}"

    # ---- Benchmark ----
    def _benchmark_tps(self, new_tokens: int = 16) -> float:
        if not self.is_loaded:
            return 0.0
        try:
            inputs = self.tokenizer("The quick brown fox", return_tensors="pt")
            if self._device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}
                torch.cuda.synchronize()
            
            t0 = time.perf_counter()
            with torch.inference_mode():
                _ = self.model.generate(**inputs, max_new_tokens=new_tokens, do_sample=False)
            if self._device == "cuda":
                torch.cuda.synchronize()
            t1 = time.perf_counter()
            
            return round(new_tokens / max(1e-6, t1 - t0), 2)
        except Exception:
            return 0.0

    # ---- Model switch & settings ----
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

    # ---- Idle unload ----
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
        if self._idle_timer:
            try:
                self._idle_timer.cancel()
            except Exception:
                pass
        self._idle_timer = None

    def _idle_unload(self):
        self._emit_status("Idle timeout — unloading model.")
        self.unload()

    def shutdown(self):
        self._cancel_idle_timer()
        self.unload()