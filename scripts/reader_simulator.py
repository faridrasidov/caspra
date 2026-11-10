"""Reader protocol simulator with a durable, conservative activation journal."""

import argparse
import asyncio
from contextlib import closing
from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from uuid import UUID

import httpx


class DefiniteActivationError(Exception):
    """The driver knows the physical action did not happen."""


class ReaderJournal:
    def __init__(self, path):
        self.path = str(path)
        with closing(self.connect()) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS taps (tap_key TEXT PRIMARY KEY, "
                "card_uid TEXT NOT NULL, play_id TEXT UNIQUE, deadline TEXT, state TEXT NOT NULL)"
            )

    def connect(self):
        db = sqlite3.connect(self.path, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        return db

    def prepare(self, tap_key, card_uid):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM taps WHERE tap_key=?", (str(tap_key),)).fetchone()
            if row and row["card_uid"] != card_uid:
                raise ValueError("Tap key belongs to another card")
            db.execute(
                "INSERT OR IGNORE INTO taps(tap_key,card_uid,state) VALUES (?,?,'prepared')",
                (str(tap_key), card_uid),
            )
            db.commit()

    def authorize(self, tap_key, play):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM taps WHERE tap_key=?", (str(tap_key),)).fetchone()
            if row is None or (row["play_id"] and row["play_id"] != play["id"]):
                raise ValueError("Play does not match journal")
            if row["state"] == "prepared":
                db.execute(
                    "UPDATE taps SET play_id=?,deadline=?,state='authorized' WHERE tap_key=?",
                    (play["id"], play["execute_before"], str(tap_key)),
                )
            db.commit()

    def activate(self, tap_key, pulse):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM taps WHERE tap_key=?", (str(tap_key),)).fetchone()
            if row is None or row["state"] == "prepared":
                raise ValueError("Authorize the tap before activation")
            if row["state"] != "authorized":
                db.commit()
                return "unknown" if row["state"] == "executing" else row["state"]
            deadline = datetime.fromisoformat(row["deadline"])
            if deadline.tzinfo is None:
                raise ValueError("Activation deadline must include a timezone")
            if deadline <= datetime.now(UTC):
                db.execute("UPDATE taps SET state='failed' WHERE tap_key=?", (str(tap_key),))
                db.commit()
                return "failed"
            # Commit before the physical effect. A crash from here requires review.
            db.execute("UPDATE taps SET state='executing' WHERE tap_key=?", (str(tap_key),))
            db.commit()
            try:
                pulse()
                outcome = "activated"
            except DefiniteActivationError:
                outcome = "failed"
            except (OSError, TimeoutError):
                outcome = "unknown"
            db.execute("UPDATE taps SET state=? WHERE tap_key=?", (outcome, str(tap_key)))
            return outcome


class ReaderSimulator:
    def __init__(self, client, device_id, secret, journal):
        self.client, self.device_id, self.secret, self.journal = (
            client,
            str(device_id),
            secret,
            journal,
        )

    async def request(self, path, payload):
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp, nonce = str(int(time.time())), secrets.token_urlsafe(24)
        body_hash = hashlib.sha256(body).hexdigest()
        message = (f"POST\n{path}\n{self.device_id}\n{timestamp}\n{nonce}\n{body_hash}").encode()
        signature = hmac.new(self.secret.encode(), message, hashlib.sha256).hexdigest()
        response = await self.client.post(
            path,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Device-Id": self.device_id,
                "X-Device-Timestamp": timestamp,
                "X-Device-Nonce": nonce,
                "X-Device-Signature-Version": "2",
                "X-Device-Signature": signature,
            },
        )
        response.raise_for_status()
        return response.json()

    async def tap(self, tap_key, card_uid, pulse):
        self.journal.prepare(tap_key, card_uid)
        play = await self.request(
            "/device/api/v1/plays", {"card_uid": card_uid, "idempotency_key": str(tap_key)}
        )
        if play["status"] in {"activated", "refunded"}:
            return play
        self.journal.authorize(tap_key, play)
        if play["status"] == "unknown":
            # Only a locally recorded final result can resolve a server uncertainty.
            with closing(self.journal.connect()) as db:
                state = db.execute(
                    "SELECT state FROM taps WHERE tap_key=?", (str(tap_key),)
                ).fetchone()["state"]
            outcome = state if state in {"activated", "failed"} else "unknown"
        else:
            outcome = self.journal.activate(tap_key, pulse)
        return await self.request(
            f"/device/api/v1/plays/{play['id']}/outcome", {"outcome": outcome}
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--device-id", type=UUID, required=True)
    parser.add_argument("--secret-env", default="CASPRA_READER_SECRET")
    parser.add_argument(
        "--tap-key",
        type=UUID,
        required=True,
        help="Reuse the same key when recovering the same tap",
    )
    parser.add_argument("--card-uid", required=True)
    parser.add_argument("--journal", type=Path, default=Path("reader-journal.sqlite"))
    parser.add_argument("--fail-activation", action="store_true")
    args = parser.parse_args()
    secret = os.environ.get(args.secret_env)
    if not secret:
        parser.error("Set the reader secret environment variable")

    def pulse():
        if args.fail_activation:
            raise DefiniteActivationError("Simulation: no pulse was sent")

    async with httpx.AsyncClient(base_url=args.base_url, timeout=10) as client:
        result = await ReaderSimulator(
            client, args.device_id, secret, ReaderJournal(args.journal)
        ).tap(args.tap_key, args.card_uid, pulse)
        print(json.dumps({"play_id": result["id"], "status": result["status"]}))


if __name__ == "__main__":
    asyncio.run(main())
