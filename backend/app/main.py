"""FastAPI entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import admin, assessments, auth, catalogue
from app.services.predictor import get_predictor


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load the model at startup so a missing or incompatible model file stops the server
    # booting, instead of failing on the first real assessment.
    get_predictor()
    yield


app = FastAPI(
    title="CHV Symptom Triage",
    description=(
        "Decision support for community health volunteers. Returns a likely illness with a "
        "confidence score and referral guidance. **Not a diagnosis.** Danger signs are "
        "checked before the model and always trigger urgent referral."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(catalogue.router)
app.include_router(assessments.router)
app.include_router(admin.router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness check, with the model version and data hash being served."""
    predictor = get_predictor()
    return {
        "status": "ok",
        "model_version": get_settings().model_version,
        "config_hash": predictor.config_hash[:12],
    }
