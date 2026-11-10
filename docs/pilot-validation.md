# Local validation, 2026-11-10

Validated on Windows with Python 3.14 and Node/Chromium. Application source also
passes a Python 3.13 syntax check; the Docker image and CI target Python 3.13.

| Check | Result |
| --- | --- |
| Complete backend suite | 108 passed, 6 PostgreSQL-only tests skipped |
| Operator browser regressions | 4 passed, desktop and Pixel 7 Chromium |
| Browser flows against disposable real API | 4 passed, desktop and Pixel 7 Chromium |
| Real API browser page errors | None in the exercised workflows |
| Ruff lint and format | Passed |
| Generated OpenAPI / TypeScript types | Regenerated; type check passed |
| Production frontend build and icon check | Passed |
| Python requirements security audit | No known vulnerabilities |
| Production frontend dependency audit | No known vulnerabilities |
| Migration | One head; 19 distinct frozen new tables; SQL generation passed |
| Reader journal | Replay, deadline expiry, and simulated power-loss tests passed |

The real API browser tests cover cashier funding/receipt/shift reconciliation,
customer enrollment and lost-card reporting, reader provisioning, machine price
configuration, signed play authorization, uncertain activation, manager resolution,
refund, and machine reporting. Screenshots were inspected for desktop and mobile.
Playwright screenshots are under the OS temporary directories
`caspra-playwright-real` and `caspra-playwright-mock`.

The production main JavaScript chunk is 90.34 kB (31.22 kB gzip), compared with
2,769.83 kB before the icon factory tree-shaking fix. This measures the main chunk,
not the complete application or server latency.

PostgreSQL trigger/concurrency tests are wired into CI against migrated disposable
schemas. They were not executed locally because PostgreSQL is unavailable here.
No live database migration or deployment was performed. Synthetic benchmark
seeding/load CLIs were added and their entry points checked; the million-row,
100-reader, 30-minute load run has not been executed. Hardware activation and
durability need actual readers and machines. Live payments remain unavailable
pending provider selection; offline machine spending remains disabled.
