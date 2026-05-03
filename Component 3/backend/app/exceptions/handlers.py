import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions.app_exceptions import AppException
from app.model.response_models import GenericResponse


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        payload = GenericResponse[dict].failed_response(
            message=exc.message,
            error_code=exc.error_code,
            status_code=exc.status_code,
            data=None,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        payload = GenericResponse[dict].failed_response(
            message=str(exc.detail),
            error_code="HTTP_EXCEPTION",
            status_code=exc.status_code,
            data=None,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        payload = GenericResponse[dict].failed_response(
            message="Request validation failed.",
            error_code="VALIDATION_ERROR",
            status_code=422,
            data={"details": exc.errors()},
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception occurred.")
        payload = GenericResponse[dict].failed_response(
            message="Internal server error.",
            error_code="INTERNAL_SERVER_ERROR",
            status_code=500,
            data=None,
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

