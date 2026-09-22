"""FastAPI entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="CHV Symptom Triage",
    description=(
        "Decision support for community health volunteers. "
        "Returns a likely illness with a confidence score and referral guidance. "
        "Not a diagnosis."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
