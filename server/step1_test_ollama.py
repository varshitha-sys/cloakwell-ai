"""
Step 1: Confirm Ollama + Python are talking.
Run: python step1_test_ollama.py
Requires: `ollama pull gemma3:4b` already done, and Ollama running in the background
(it usually auto-starts after install; if not, run `ollama serve` in another terminal).
"""
import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"

def ask_ollama(prompt: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["response"]

if __name__ == "__main__":
    test_prompt = "Say hello in exactly five words."
    print("Sending prompt to Gemma...")
    result = ask_ollama(test_prompt)
    print("Gemma replied:")
    print(result)