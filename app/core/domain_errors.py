# app/core/domain_errors.py

from fastapi import HTTPException, status


class DomainError(HTTPException):
    """Base domain error mapped to an HTTP response."""

    code = "domain_error"

    def __init__(self, status_code: int, detail: str, *, code: str | None = None) -> None:
        self.code = code or self.code
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(DomainError):
    code = "not_found"

    def __init__(self, resource: str, identifier: str | None = None) -> None:
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(DomainError):
    code = "conflict"

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            code=code,
        )


class ValidationError(DomainError):
    code = "validation_error"

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


class InsufficientFundsError(DomainError):
    code = "insufficient_funds"

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient funds",
        )


class UnauthorizedError(DomainError):
    code = "unauthorized"

    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenError(DomainError):
    code = "forbidden"

    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ServiceUnavailableError(DomainError):
    code = "service_unavailable"

    def __init__(self, detail: str = "Required service is unavailable") -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class TooManyRequestsError(DomainError):
    code = "rate_limit_exceeded"

    def __init__(self, detail: str = "Too many requests") -> None:
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
