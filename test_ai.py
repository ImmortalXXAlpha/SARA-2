# test_ai.py
import time
import traceback
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

model_name = "mistralai/Mistral-7B-Instruct-v0.2"

def print_header():
    print("="*60)
    print(f"Model: {model_name}")
    print("PyTorch / CUDA environment:")
    print(" torch.version.cuda:", torch.version.cuda)
    print(" torch.cuda.is_available():", torch.cuda.is_available())
    if torch.cuda.is_available():
        try:
            print(" torch.cuda.device_count():", torch.cuda.device_count())
            print(" torch.cuda.get_device_name(0):", torch.cuda.get_device_name(0))
        except Exception:
            pass
    print("="*60)

def load_model_quantized(model_name):
    """
    Load using bitsandbytes quantization with the recommended new API.
    Adjust `load_in_4bit`/8bit via BitsAndBytesConfig.
    """
    print("Preparing BitsAndBytesConfig...")
    # Choose 8-bit (if you want 4-bit change load_in_4bit=True and config accordingly)
    bnb_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0  # optional tuning param
    )

    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    print("Tokenizer loaded.")

    print("Loading model (quantized) - this may take a minute or two...")
    # device_map="auto" tries to partition across devices. If you want to force GPU only (may OOM) use device_map={"":0}
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        dtype=torch.float16,   # new arg instead of torch_dtype
        trust_remote_code=True  # some community models require this
    )
    print("Model loaded.")
    return tokenizer, model

def simple_generate(tokenizer, model, prompt, max_new_tokens=128):
    print("Encoding prompt and moving to device...")
    inputs = tokenizer(prompt, return_tensors="pt")
    # Move inputs to model device(s) - accelerate hooks will handle per-layer movement,
    # but we move input_ids explicitly to the first device to avoid obvious CPU->GPU transfer.
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k,v in inputs.items()}

    print("Generating (this may take several seconds)...")
    t0 = time.time()
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.2,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id
    )
    elapsed = time.time() - t0
    print(f"Generation took {elapsed:.1f}s")
    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return text

def main():
    print_header()

    # Quick sanity: if no CUDA, warn
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available. This will be very slow. Consider installing GPU drivers or using GGUF+llama-cpp.")
        # still proceed on CPU for testing

    try:
        tokenizer, model = load_model_quantized(model_name)
    except Exception as e:
        print("ERROR loading quantized model with bitsandbytes/transformers:")
        traceback.print_exc()
        print("\nPossible fixes:")
        print("- Ensure bitsandbytes is installed and compatible with your CUDA and Python.")
        print("- Ensure torch/torchvision versions are compatible (CUDA build).")
        print("- Consider using a GGUF + llama-cpp-python runtime for faster local inference.")
        return

    # Confirm model device
    print("Model first param device:", next(model.parameters()).device)

    # Simple test prompt
    prompt = "You are SARA, a Windows system repair assistant. In 3 bullet points, how do you check disk corruption?"
    print("Prompt:", prompt)
    try:
        result = simple_generate(tokenizer, model, prompt, max_new_tokens=120)
        print("="*40)
        print("RAW OUTPUT:")
        print(result)
        print("="*40)
    except KeyboardInterrupt:
        print("Generation canceled by user.")
    except Exception:
        print("Generation failed:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
