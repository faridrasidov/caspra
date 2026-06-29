# app/api/docs.py

from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from scalar_fastapi import get_scalar_api_reference

from app.core.config import settings


def _filter_openapi_by_prefix(full_schema: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Return a copy of the OpenAPI schema containing only paths under `prefix`."""
    schema = deepcopy(full_schema)
    schema["paths"] = {
        path: item for path, item in full_schema.get("paths", {}).items() if path.startswith(prefix)
    }
    return schema


def register_docs(app: FastAPI) -> None:
    """Mount Scalar API reference pages and per-surface filtered OpenAPI specs.

    - One combined reference at ``/scalar`` (all surfaces via a source dropdown).
    - Per-surface references at ``/{surface}/docs`` backed by filtered specs at
      ``/openapi/{surface}.json`` so third-party developers viewing the public docs
      never see admin or device endpoints.
    """

    surfaces = {
        "admin": settings.admin_api_prefix,
        "device": settings.device_api_prefix,
        "public": settings.public_api_prefix,
    }

    def _make_spec_route(prefix: str):
        async def _spec() -> JSONResponse:
            return JSONResponse(_filter_openapi_by_prefix(app.openapi(), prefix))

        return _spec

    def _make_docs_route(surface: str, title: str):
        async def _docs() -> HTMLResponse:
            return get_scalar_api_reference(
                openapi_url=f"/openapi/{surface}.json",
                title=title,
            )

        return _docs

    for surface, prefix in surfaces.items():
        app.add_api_route(
            f"/openapi/{surface}.json",
            _make_spec_route(prefix),
            include_in_schema=False,
            methods=["GET"],
        )
        app.add_api_route(
            f"/{surface}/docs",
            _make_docs_route(surface, f"{settings.app_name} — {surface.title()} API"),
            include_in_schema=False,
            methods=["GET"],
        )

    async def _scalar_all() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{settings.app_name} — All APIs",
        )

    app.add_api_route(
        "/scalar",
        _scalar_all,
        include_in_schema=False,
        methods=["GET"],
    )
