# app/core/domain_errors.py

from fastapi import HTTPException, status


class DomainError(HTTPException):
    """Base domain error mapped to an HTTP response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(DomainError):
    def __init__(self, resource: str, identifier: str | None = None) -> None:
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class InsufficientFundsError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient funds",
        )


class UnauthorizedError(DomainError):
    def __init__(self, detail: str = "Not authenticated") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenError(DomainError):
    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
