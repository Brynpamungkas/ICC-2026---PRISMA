"""Application factory. No model calls or storage writes occur during import/startup."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from backend.app.api.routes import ApiError, ApiServices, LogStore, create_router
from backend.app.config import ROOT, load_config
from backend.app.schemas.api import ErrorDetail, HttpErrorResponse


def error_response(status: int, code: str, message: str) -> JSONResponse:
    body = HttpErrorResponse(error=ErrorDetail(code=code, message=message, id_log=None))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app(config: dict | None = None) -> FastAPI:
    cfg = load_config() if config is None else config
    directory = Path(cfg["api"]["log_dir"])
    if not directory.is_absolute():
        directory = ROOT / directory
    if cfg["api"]["health_timeout_s"] <= 0:
        raise ValueError("api.health_timeout_s must be positive")
    app = FastAPI(title="PRISMA", version=str(cfg["api"]["version"]),
                  docs_url=None, redoc_url=None, openapi_url=None,
                  responses={int(status): {"model": HttpErrorResponse} for status in (
                      HTTPStatus.UNPROCESSABLE_ENTITY, HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT,
                      HTTPStatus.SERVICE_UNAVAILABLE, HTTPStatus.INTERNAL_SERVER_ERROR)})
    app.state.api_services = ApiServices(config=cfg, store=LogStore(directory))
    app.include_router(create_router())

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_REQUEST", "Permintaan tidak valid.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(exc.status_code, "HTTP_ERROR", "Permintaan belum dapat diselesaikan.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR",
                              "Permintaan belum dapat diselesaikan.")

    @app.middleware("http")
    async def reject_get_body(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method == "GET" and await request.body():
            return error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "INVALID_REQUEST", "GET tidak menerima body.")
        return await call_next(request)

    return app


def main() -> None:
    import uvicorn
    cfg = load_config()
    uvicorn.run(create_app(cfg), host=cfg["api"]["host"], port=cfg["api"]["port"])


if __name__ == "__main__":
    main()
