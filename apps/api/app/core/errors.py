"""One standard error shape for every failure: {"error": {code, message, request_id, details}}."""

from typing import Any, cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)

_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class FieldError(BaseModel):
    field: str
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Raise (a subclass of) this from services and routes. Never raise raw HTTPException."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class BadRequestError(AppError):
    status_code, code = 400, "bad_request"


class UnauthenticatedError(AppError):
    status_code, code = 401, "unauthenticated"


class PermissionDeniedError(AppError):
    status_code, code = 403, "forbidden"


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class ConflictError(AppError):
    status_code, code = 409, "conflict"


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[FieldError] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details)
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=status_code, headers=headers
    )


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(AppError, exc)
    return _response(request, exc.status_code, exc.code, exc.message)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code = _CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _response(request, exc.status_code, code, message)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    # Deliberately excludes the submitted input so secrets are never echoed back.
    details = [
        FieldError(
            field=".".join(str(p) for p in err["loc"]),
            message=err["msg"],
            type=err["type"],
        )
        for err in exc.errors()
    ]
    return _response(request, 422, "validation_error", "The request is not valid.", details)


async def _rate_limited(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RateLimitExceeded, exc)
    return _response(request, 429, "rate_limited", "Too many requests. Please try again shortly.")


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", path=request.url.path)
    return _response(request, 500, "internal_error", "Something went wrong on our side.")


def register_error_handlers(app: FastAPI) -> None:
    handlers: dict[Any, Any] = {
        AppError: _app_error,
        StarletteHTTPException: _http_error,
        RequestValidationError: _validation_error,
        RateLimitExceeded: _rate_limited,
        Exception: _unhandled,
    }
    for exc_type, handler in handlers.items():
        app.add_exception_handler(exc_type, handler)


COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {
        "model": ErrorResponse,
        "description": _CODES[status].replace("_", " ").title(),
    }
    for status in (400, 401, 403, 404, 409, 422, 429)
}
