# Arcade pilot implementation and rollout

## Decisions

The first venue is an arcade. Spending requires a live server authorization.
Paid credit uses the venue's configured ISO currency; bonus credit is a separate
wallet liability. The venue currency, payment provider, and installed machine count
are still to be selected. USD in examples and synthetic fixtures is a placeholder.
Amounts in every API are integer minor units; the UI uses each currency's exponent.

`PAYMENT_PROVIDER=disabled` is the deployment default. The sandbox adapter runs
only outside production and in testing or venues with a `sandbox-` slug. It never
takes a real payment. Production rejects sandbox configuration at startup.

## Delivered workflows

| Area | Behavior |
| --- | --- |
| Ledger | Atomic paid/bonus posting, bonus-first machine purchases, immutable allocations, proportional cumulative refunds, hold-safe paid transfers |
| Staff | Owner, manager, cashier, technician permission templates; tenant isolation; session revocation on access/password changes; last-owner protection |
| Machines | One reader per machine, server prices and revisions, local-time happy-hour schedules, unavailable/maintenance states |
| Plays | Atomic charge plus authorization, fixed price snapshot, 30-second activation deadline, reader outcome and manager review |
| Cashier | One open shift per cashier/terminal, packages, receipts, signed cash movements, counted/expected cash and manager variance review |
| Customers | Customer workspace, lost-card blocking and replacement, single-use enrollment/recovery links, separate portal sessions |
| Families | One guardian per child, paid-credit allocation, currency-specific daily spend limits, no nested guardianship |
| Reporting | Tenant aggregates, separated currencies and paid/bonus amounts, venue days, machine outcomes/revenue/refunds, recorded reader outages |
| Operations | Scheduled reconciliation, automatic financial pause on differences, audited cache repair, owner reopening, persistent exception alerts |
| History | Server filters/search, stable timestamp/ID cursor, leased background CSV/JSONL exports with authenticated downloads |

The customer portal is `/portal`. The operator dashboard includes Machines,
Machine plays, Cashier shifts, Packages & pricing, Families, Operational alerts,
Staff access, and Machine reports. Backend surfaces are `/admin/api/v1`,
`/device/api/v1`, `/public/api/v1`, and `/customer/api/v1`.

## Financial semantics

A package creates one receipt, a paid-credit transaction, and an optional bonus
grant in the same database transaction. Cash expectations include paid receipts
and signed cash movements; bonus grants do not increase the cash drawer.
Paid transfers cannot move bonus balances or consume held funds. Daily allowances
count posted purchases/captures across the customer's wallets in that currency.
Refunds of today's purchases restore that day's allowance; transfers do not
count as spending. Venue days use the configured timezone.

Machine purchases record funding allocations. Partial refunds use cumulative
proportions so multiple partial refunds restore the exact original paid/bonus
amounts when completed. A refund creates compensating ledger entries; posted
entries and allocations are never edited. A fully refunded play retains its
activation outcome separately for reporting.

Financial pause blocks new ledger writes, including refunds. The owner investigates
the reconciliation report, rebuilds a corrupt **cache** from unchanged entries if
appropriate, reruns reconciliation, and explicitly reopens writes with a reason.
Cache repair does not clear the pause or alter ledger history. In-flight transactions
can finish while a newly detected pause is being recorded.

Reports use repeatable-read PostgreSQL snapshots. "Today" is independent of a
selected historical range. Machine refunds are reported on their refund date;
net paid spend can therefore be negative in a period. Reader downtime is observed
heartbeat downtime, not proof of physical machine uptime. Monitoring begins at
deployment; historical outages cannot be reconstructed.

## Deployment

1. Back up the database and test restoration into an isolated database. Inspect
   duplicate nonclosed `(tenant, customer, type, currency)` wallet buckets; the
   migration refuses duplicates instead of choosing a balance to retain.
2. Deploy revision `c6b2a8d41590` using `alembic upgrade head` before the new API or
   workers. It creates 19 tables, indexes, permission templates, and ledger ownership
   and allocation immutability guards. This financial migration is forward-only.
3. Run API, Celery worker, and exactly one Celery beat scheduler. Maintenance runs
   every 30 seconds, reconciliation every 5 minutes, and export pickup every 5 seconds.
4. Share the export volume between API and worker; set `EXPORT_DIRECTORY` to that
   directory. Downloads require the creating staff user's current authenticated
   session. Files expire after 24 hours. CSV formula prefixes are escaped.
5. Configure venue currency/timezone and locations. Create named staff users, register
   readers as owner, securely provision the once-shown secret, and bind each reader
   to a machine. New readers have legacy arbitrary-amount payments disabled.
6. Keep offline spending disabled and live online payment unavailable. Run the gates
   below, then open a supervised cashier shift and a small machine pilot.

Existing devices are grandfathered into the legacy payment capability by migration
to preserve old integrations. Binding one to a machine disables use of the legacy
arbitrary-amount routes for that reader. Inventory and retire those capabilities
before widening the rollout. HMAC v2 is mandatory for play authorization.

Use [the reader contract](reader-contract.md) for firmware integration and
[operations](operations.md) for backup and incident handling.

## Validation commands and gates

See [the local validation record](pilot-validation.md) for completed checks and
the distinction between local verification and deployment gates.

Local regression tests use disposable SQLite fixtures. PostgreSQL tests require
an explicitly selected database whose name ends in `_test`; every test migrates a
fresh generated schema rather than using `metadata.create_all`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --show-capture=no -o log_level=WARNING
# Set DATABASE_URL to the isolated PostgreSQL *_test database, then repeat.
.\.venv\Scripts\python.exe scripts/gen_openapi.py
cd web
npm ci
npm run generate:api
npm run typecheck
npm run build
npm run check:icons
npm run test:e2e
$env:CASPRA_E2E_REAL='1'
npm run test:e2e -- pilot-live.spec.ts
```

The browser integration server uses a temporary local database and synthetic
credentials. It exercises cash funding, exact shift closing, customer enrollment,
and lost-card reporting on desktop and mobile, with screenshots and page-error
checks. Screenshots and traces go to the operating system's temporary directory.
Mocked browser tests cover loading/error states and existing operator actions.

Before production, require a passing migrated PostgreSQL suite, a restored backup
with healthy reconciliation, real reader failure/power-loss testing, and a measured
load run. Local SQLite success does not establish PostgreSQL concurrency correctness,
deployment health, physical activation safety, or production throughput.

## Reproducible performance fixture

Create a **new disposable** PostgreSQL database ending in `_bench`; the seeder
refuses a database containing a venue and never deletes one. Supply strong test
secrets through environment variables. The fixture defaults to 100 synthetic
readers and 1,000,000 history transactions with balanced ledger entries and matching
wallet caches. Keep `.benchmark/manifest.json` local; it contains synthetic secrets.

```powershell
# DATABASE_URL points exclusively to the new *_bench database.
# Set CASPRA_BENCH_PASSWORD to the synthetic owner's password.
.\.venv\Scripts\python.exe -m scripts.seed_benchmark
# Start API + Redis + worker + beat against that same disposable DB, then:
.\.venv\Scripts\python.exe -m scripts.benchmark_pilot --base-url http://127.0.0.1:8000 --manifest .benchmark/manifest.json --email owner@benchmark.test --seconds 1800 --rate 20 --output .benchmark/result.json
```

The runner sends authorization/outcome pairs without operating hardware and reads
overview/history concurrently. It writes latency percentiles, request errors,
reader count, target rate, maximum concurrency, and final reconciliation health.
Record CPU, memory, database connection/lock metrics and an `EXPLAIN (ANALYZE,
BUFFERS)` sample alongside the JSON. Suggested initial acceptance targets are
zero financial differences, zero unexpected errors, purchase p95 below 500 ms,
and overview/history p95 below 1 second. These are targets, not measured claims.
Venue sizing remains a placeholder until that run is completed on the target host.

## Payment adapter handoff

`PaymentProvider` defines checkout creation, signed notification validation, and
authoritative payment verification. A chosen live provider must implement these
and add its authenticated webhook endpoint. Verify reference, customer/tenant,
amount, currency, and final provider status before crediting the stored checkout
snapshot. Deliver notifications at least once, use the checkout's idempotency key,
and commit receipt, paid/bonus credits, and confirmed checkout atomically.
Do not trust browser redirects as settlement. Add failure, signature, mismatch,
retry, and refund tests before exposing live payment UI. Real provider fees,
settlement reconciliation, refunds/chargebacks, and country requirements remain
provider-selection work; no live integration is implied by the sandbox.
