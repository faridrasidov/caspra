# app/schemas/health.py

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    version: str
