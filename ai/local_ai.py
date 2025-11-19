import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import threading

class LocalAI:
    def __init__(self, model_name="mistralai/Mistral-7B-Instruct-v0.2"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.is_loading = False
        self.is_loaded = False
        
    def load_model(self):
        """Load model in background thread"""
        if self.is_loaded or self.is_loading:
            return
        
        self.is_loading = True
        thread = threading.Thread(target=self._load_model_thread)
        thread.daemon = True
        thread.start()
    
    def _load_model_thread(self):
        """Background thread to load model"""
        try:
            print(f"🔄 Loading {self.model_name}...")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Load model (8-bit quantization to save memory)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                #load_in_8bit=True,  # Reduces memory usage
                device_map="auto",
                torch_dtype=torch.float16
            )
            
            self.is_loaded = True
            self.is_loading = False
            print(f"✅ Model loaded successfully on {self.device}")
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.is_loading = False
    
    def generate(self, prompt, max_length=512, temperature=0.7):
        """Generate response from prompt"""
        if not self.is_loaded:
            return "⚠️ Model is still loading. Please wait..."
        
        try:
            # Format prompt for instruction model
            formatted_prompt = f"[INST] {prompt} [/INST]"
            
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=max_length,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove the prompt from response
            response = response.replace(formatted_prompt, "").strip()
            
            return response
            
        except Exception as e:
            return f"❌ Error generating response: {e}"
    
    def switch_model(self, model_name):
        """Switch to different model"""
        self.model_name = model_name
        self.is_loaded = False
        self.model = None
        self.tokenizer = None
        self.load_model()