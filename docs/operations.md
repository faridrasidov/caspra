# Caspra Pilot Operations

## Deployment

Run `alembic upgrade head` as a one-shot job before starting the API and worker.
Production startup must reject default secrets, debug mode, wildcard CORS, and an
unbounded HMAC v1 migration window.

## Backup And Restore

1. Create daily encrypted PostgreSQL custom-format backups with `pg_dump -Fc`.
2. Retain seven daily, four weekly, and twelve monthly copies in separate storage.
3. Record the database revision with every backup.
4. Restore monthly into an isolated database, run `alembic upgrade head`, then call
   `/admin/api/v1/ledger/reconciliation`.
5. A restore is accepted only when every transaction balances and every wallet
   cache agrees with its immutable entries.

## Incident Gates

- Disable wallet writes when reconciliation reports a difference.
- Disable HMAC v1 at its configured sunset even if a reader has not migrated.
- Disable offline acceptance when queue age, device exposure, or rejection alerts fire.
- Preserve ledger and audit rows; repair through compensating entries only.
