"""FastAPI app: middleware, error mapping and the router.

1. Read allowed browser origins from `CORS_ORIGINS` (comma-separated).
2. Enable CORS for the JSON API, including the `X-API-Key` header.
3. Map our own errors to their HTTP status (`CropseqError.http_status`).
4. Map any httpx upstream failure to 504, so a dead SoilGrids/weather API is not
   reported as a backend crash.
5. Run with: uv run uvicorn cropseq.api.main:app
"""

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import config
from ..errors import CropseqError
from .routes import router

UPSTREAM_MESSAGE = (
    "A weather or soil data service is unavailable right now. Try again shortly."
)


def _allowed_origins() -> list[str]:
    return [item.strip() for item in config.cors_origins.split(",") if item.strip()]


def create_app() -> FastAPI:
    app = FastAPI(title="cropseq", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    app.include_router(router)

    @app.exception_handler(CropseqError)
    async def cropseq_error(request: Request, exc: CropseqError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status, content={"detail": exc.message}
        )

    @app.exception_handler(httpx.HTTPError)
    async def upstream_error(request: Request, exc: httpx.HTTPError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": UPSTREAM_MESSAGE})

    return app


app = create_app()
