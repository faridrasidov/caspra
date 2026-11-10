"""Opt-in load runner for an isolated sandbox venue; never creates physical pulses.

Manifest format: {"venue_slug":"sandbox-benchmark", "readers":[
  {"device_id":"uuid", "secret":"test-secret", "card_uid":"test-card"}]}
Run only against dedicated synthetic data. Secrets stay in the local manifest.
"""

import argparse
import asyncio
from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import statistics
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from scripts.reader_simulator import ReaderSimulator


class PilotBenchmark:
    def __init__(self, args, manifest):
        self.args, self.manifest = args, manifest
        self.latencies, self.admin_latencies = [], []
        self.errors = Counter()
        self.inflight = set()
        self.maximum_inflight = 0

    async def play(self, client, reader):
        start = time.perf_counter()
        simulator = ReaderSimulator(client, reader["device_id"], reader["secret"], None)
        try:
            result = await simulator.request(
                "/device/api/v1/plays",
                {"card_uid": reader["card_uid"], "idempotency_key": str(uuid4())},
            )
            await simulator.request(
                f"/device/api/v1/plays/{result['id']}/outcome", {"outcome": "activated"}
            )
            self.latencies.append(time.perf_counter() - start)
        except (httpx.HTTPError, KeyError) as error:
            status = (
                error.response.status_code
                if isinstance(error, httpx.HTTPStatusError)
                else type(error).__name__
            )
            self.errors[str(status)] += 1

    async def admin_reads(self, client, stop):
        while time.perf_counter() < stop:
            for path in ["/overview", "/transactions/history?limit=20"]:
                start = time.perf_counter()
                try:
                    headers = {"Authorization": f"Bearer {self.token}"}
                    response = await client.get("/admin/api/v1" + path, headers=headers)
                    if response.status_code == 401:
                        refresh = await client.post("/admin/api/v1/auth/refresh")
                        refresh.raise_for_status()
                        self.token = refresh.json()["access_token"]
                        response = await client.get(
                            "/admin/api/v1" + path,
                            headers={"Authorization": f"Bearer {self.token}"},
                        )
                    response.raise_for_status()
                    self.admin_latencies.append(time.perf_counter() - start)
                except httpx.HTTPError as error:
                    self.errors[f"admin:{type(error).__name__}"] += 1
            await asyncio.sleep(1)

    @staticmethod
    def summary(values):
        ordered = sorted(values)
        return {
            "count": len(values),
            "p50_ms": statistics.median(values) * 1000 if values else None,
            "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000
            if ordered
            else None,
            "maximum_ms": max(values) * 1000 if values else None,
        }

    async def run(self):
        async with httpx.AsyncClient(
            base_url=self.args.base_url, timeout=30, limits=httpx.Limits(max_connections=200)
        ) as client:
            login = await client.post(
                "/admin/api/v1/auth/login",
                json={"email": self.args.email, "password": os.environ["CASPRA_BENCH_PASSWORD"]},
            )
            login.raise_for_status()
            token = login.json()["access_token"]
            self.token = token
            headers = {"Authorization": f"Bearer {token}"}
            venue = await client.get("/admin/api/v1/org", headers=headers)
            venue.raise_for_status()
            if venue.json()["slug"] != self.manifest["venue_slug"]:
                raise ValueError("Authenticated venue does not match the sandbox manifest")
            start = time.perf_counter()
            stop = start + self.args.seconds
            admin = asyncio.create_task(self.admin_reads(client, stop))
            index = 0
            readers = self.manifest["readers"]
            while time.perf_counter() < stop:
                if len(self.inflight) < 200:
                    task = asyncio.create_task(self.play(client, readers[index % len(readers)]))
                    self.inflight.add(task)
                    task.add_done_callback(self.inflight.discard)
                    self.maximum_inflight = max(self.maximum_inflight, len(self.inflight))
                else:
                    self.errors["client_saturated"] += 1
                index += 1
                await asyncio.sleep(max(0, start + index / self.args.rate - time.perf_counter()))
            await asyncio.gather(*self.inflight, admin)
            reconciliation = await client.post(
                "/admin/api/v1/ledger/reconciliation/run",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            reconciliation.raise_for_status()
            report = {
                "generated_at": datetime.now(UTC).isoformat(),
                "duration_seconds": self.args.seconds,
                "target_plays_per_second": self.args.rate,
                "reader_count": len(readers),
                "maximum_inflight": self.maximum_inflight,
                "plays": self.summary(self.latencies),
                "admin_reads": self.summary(self.admin_latencies),
                "errors": dict(self.errors),
                "reconciliation_healthy": reconciliation.json()["healthy"],
            }
            self.args.output.write_text(json.dumps(report, indent=2), encoding="utf8")
            print(json.dumps(report, indent=2))
            return not self.errors and report["reconciliation_healthy"]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--output", type=Path, default=Path("benchmark-result.json"))
    args = parser.parse_args()
    if not os.environ.get("CASPRA_BENCH_PASSWORD"):
        parser.error("Set CASPRA_BENCH_PASSWORD for the sandbox owner")
    if (
        urlparse(args.base_url).scheme not in {"http", "https"}
        or args.seconds <= 0
        or args.rate <= 0
    ):
        parser.error("Use an HTTP URL and positive duration/rate")
    manifest = json.loads(args.manifest.read_text(encoding="utf8"))
    if not manifest.get("venue_slug", "").startswith("sandbox-") or not manifest.get("readers"):
        parser.error("A nonempty sandbox venue manifest is required")
    if not await PilotBenchmark(args, manifest).run():
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
