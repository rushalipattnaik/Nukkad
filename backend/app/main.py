from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.rate_limit import limiter
from app.db.database import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    if not settings.serpapi_api_key:
        logger.warning("SERPAPI_API_KEY is not set - scans will fail until it is configured in .env")
    if not (settings.gemini_api_key and settings.gemini_model):
        logger.warning("Gemini is not fully configured - the app will use deterministic templates instead of LLM narration")
    yield


app = FastAPI(title="Nukkad API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internal details (stack traces, file paths) to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "nukkad-api", "docs": "/docs"}