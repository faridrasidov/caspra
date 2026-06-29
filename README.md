# Caspra Backend

FastAPI backend for **Caspra** — multi-tenant RFID/NFC stored-value ledger platform.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt -r requirements-test.txt
cp .env.example .env            # edit secrets
uvicorn app.main:app --reload
```

## API docs

- Swagger UI: http://localhost:8000/docs
- OpenAPI export: `python scripts/gen_openapi.py` → `openapi.json`

## Tests

```bash
pytest
```

## Project layout

```
app/
  api/v1/endpoints/   # thin HTTP routes
  services/           # business logic
  models/             # SQLAlchemy ORM (by domain)
  schemas/            # Pydantic DTOs
  core/               # config, security, errors
  engines/            # authorization, pricing
  workers/            # background jobs
tests/
  integration/        # HTTP tests
  ledger/             # money correctness tests
migrations/           # Alembic
```

## Related repos

- `caspra-node` — reader / edge gateway agents
- `caspra-frontend` — admin + user dashboards
