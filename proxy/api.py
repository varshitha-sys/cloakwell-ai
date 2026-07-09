"""
Thin HTTP surface over the classification core (engine.classify).

This is NOT a separate backend service — it's a lightweight FastAPI wrapper that
reuses the exact same detection pipeline the mitmproxy addon calls in-process, so
the browser extension and dashboard get identical verdicts. /logs and /stats
arrive with the SQLite logger in a later task.

Run:  uvicorn api:app --port 8000     (or: python -m uvicorn api:app)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import engine

app = FastAPI(title="AI DLP — Classification API")

# The extension and dashboard call this from other origins; open CORS for the demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClassifyRequest(BaseModel):
    text: str
    source: str = "extension"
    session_id: str = "default"
    context: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/classify")
def classify(req: ClassifyRequest):
    return engine.classify(
        req.text,
        session_id=req.session_id,
        source=req.source,
        context=req.context or None,
    )
