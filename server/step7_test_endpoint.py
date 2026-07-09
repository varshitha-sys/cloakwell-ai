"""
Step 7: Test the full pipeline through the running FastAPI server.
First run in one terminal:  uvicorn main:app --reload --port 8000
Then in another terminal:   python step7_test_endpoint.py
"""
import httpx

def main():
    payload = {
        "prompt": (
            "Summarise this complaint from Jane Doe, SSN 123-45-6789, "
            "about our unreleased Project Falcon delay."
        )
    }
    response = httpx.post(
        "http://localhost:8000/redact-and-ask", json=payload, timeout=60.0
    )
    response.raise_for_status()
    data = response.json()

    print("Redacted text that actually left the machine:")
    print(data["redacted_text"])
    print()
    print("Entities detected:")
    print(data["entities_detected"])
    print()
    print("Final answer shown to user:")
    print(data["final_response"])

if __name__ == "__main__":
    main()