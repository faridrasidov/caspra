# app/core/server_errors.py

import logging

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def log_and_raise_server_error(operation: str, exc: Exception) -> None:
    """Log unexpected failures and raise a generic 500."""
    logger.exception("Server error during %s", operation)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to {operation}",
    ) from exc
