"""FastAPI app. Run with: uv run uvicorn cropseq.api.main:app"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..errors import CropseqError
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="cropseq", version="0.1.0")
    app.include_router(router)

    @app.exception_handler(CropseqError)
    async def cropseq_error(request: Request, exc: CropseqError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status, content={"detail": exc.message}
        )

    return app


app = create_app()
