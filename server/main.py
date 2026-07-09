"""
FastAPI server exposing the redaction pipeline as an HTTP endpoint.
Run: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI
from pydantic import BaseModel

# TODO: switch back to the real import once Fireworks credits arrive:
# from step4_5_fireworks_roundtrip import redact_ask_restore
from step4_5_fireworks_mock import redact_ask_restore

app = FastAPI(title="Local Redaction Layer")


class RedactRequest(BaseModel):
    prompt: str


class RedactResponse(BaseModel):
    final_response: str
    redacted_text: str
    entities_detected: list[dict]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/redact-and-ask", response_model=RedactResponse)
def redact_and_ask(req: RedactRequest):
    result = redact_ask_restore(req.prompt)
    return RedactResponse(
        final_response=result["final_response"],
        redacted_text=result["redacted_text"],
        entities_detected=result["entities_detected"],
    )