# app/schemas/__init__.py

from pydantic import BaseModel


class PaginationSchema(BaseModel):
    page: int
    total: int
    pages: int
