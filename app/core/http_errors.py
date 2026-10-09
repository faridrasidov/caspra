from collections.abc import Awaitable, Callable
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.audit_context import AuditRequestContext, audit_request_context
from app.core.domain_errors import DomainError
from app.core.metrics import increment_metric
from app.core.request_context import request_id_context

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    request_id: str,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://caspra.dev/problems/{code}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
        media_type=PROBLEM_MEDIA_TYPE,
        headers={"X-Request-Id": request_id},
    )


def register_http_controls(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        token = request_id_context.set(request_id)
        audit_token = None
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith(
            "/admin/api/"
        ):
            audit_token = audit_request_context.set(
                AuditRequestContext(
                    method=request.method,
                    path=request.url.path,
                    request_id=request_id,
                )
            )
        started = time.perf_counter()
        response_status = 500
        try:
            response = await call_next(request)
            response_status = response.status_code
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request_complete",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response_status,
                    "duration_ms": round(elapsed_ms, 2),
                },
            )
            if audit_token is not None:
                audit_request_context.reset(audit_token)
            request_id_context.reset(token)
        response.headers["X-Request-Id"] = request_id
        increment_metric(
            "http_requests_total",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = request_id_context.get() or str(uuid4())
        if exc.status_code >= 500:
            increment_metric("http_errors_total", code="internal_error")
            cause = exc.__cause__
            logger.error(
                "Unhandled server error request_id=%s path=%s",
                request_id,
                request.url.path,
                exc_info=(
                    (type(cause), cause, cause.__traceback__)
                    if cause is not None
                    else (type(exc), exc, exc.__traceback__)
                ),
            )
            return _problem(
                request,
                status_code=exc.status_code,
                code="internal_error",
                title="Internal Server Error",
                detail="An unexpected error occurred",
                request_id=request_id,
            )
        code = exc.code if isinstance(exc, DomainError) else f"http_{exc.status_code}"
        increment_metric("http_errors_total", code=code)
        if code == "insufficient_funds":
            increment_metric("insufficient_funds_total")
            increment_metric("payment_failures_total", reason=code)
        return _problem(
            request,
            status_code=exc.status_code,
            code=code,
            title=str(code).replace("_", " ").title(),
            detail=str(exc.detail),
            request_id=request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request_id_context.get() or str(uuid4())
        return _problem(
            request,
            status_code=422,
            code="request_validation_error",
            title="Request Validation Error",
            detail="The request payload or parameters are invalid",
            request_id=request_id,
            errors=list(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_context.get() or str(uuid4())
        logger.error(
            "Unhandled exception request_id=%s path=%s",
            request_id,
            request.url.path,
            exc_info=exc,
        )
        return _problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Server Error",
            detail="An unexpected error occurred",
            request_id=request_id,
        )
