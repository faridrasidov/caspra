# Arcade reader contract v1

## Authorization

Provision one active reader per machine. Store its ID and HMAC secret securely.
Send a signed `POST /device/api/v1/auth/heartbeat` every 60 seconds with
`{"status":"online"}` and optionally `uptime_s`. Its response includes server time.
Monitoring treats more than three minutes without a heartbeat as reader downtime.
Firmware sends `POST /device/api/v1/plays` with only `card_uid` and a UUID
`idempotency_key`; it never supplies a price. Persist that tap key before sending
the request. Reuse the same key and payload after transport failures. A different
payload with the same key is a conflict. A completed replay retains its original
server price even after schedules or prices change.

Sign exact request bytes using HMAC SHA-256 and these headers:

```text
X-Device-Id: <reader UUID>
X-Device-Timestamp: <Unix seconds>
X-Device-Nonce: <fresh random nonce for each HTTP request>
X-Device-Signature-Version: 2
X-Device-Signature: <hex HMAC>

Canonical bytes:
METHOD + "\n" + PATH + "\n" + DEVICE_ID + "\n" + TIMESTAMP + "\n" +
NONCE + "\n" + SHA256_HEX(BODY)
```

The response includes play ID, transaction ID, currency, amount, price snapshot,
status, and timezone-aware `execute_before`. Server authorization and payment
commit together. A successful HTTP response alone does not prove activation.

## Physical activation and outcomes

1. Durably record authorization and deadline before any pulse.
2. Never activate after `execute_before`. Use synchronized device time.
3. Persist an `executing` journal record **before** the physical effect.
4. Send the pulse at most once and durably record its definitive outcome.
5. POST `/device/api/v1/plays/{play_id}/outcome` with `activated`, `failed`, or
   `unknown`. Retry acknowledgement with a fresh HMAC nonce and the same result.

`failed` means the reader can prove activation did not occur; the server posts one
compensating refund. A power loss after the executing marker, timeout, or ambiguous
hardware response is `unknown`. Do not pulse again or infer failure from missing
acknowledgement. Preserve the journal and request manager review. An unknown play
cannot later be automatically refunded by a reader's failure report. A reader may
confirm a durably recorded successful activation; contradictory terminal outcomes
are rejected. A manager resolves unknown plays with a required reason. Authorization
without acknowledgement becomes unknown after the deadline via maintenance.

`GET /device/api/v1/plays/{id}` retrieves the reader's own play. `activated` and
`refunded` are final. Preserve local journals until final server acknowledgement
and normal retention/backup requirements are met; replacing the journal removes
the device's evidence that a physical effect already happened.

## Reference simulator

```powershell
# Set CASPRA_READER_SECRET to the synthetic/provisioned reader's secret.
.\.venv\Scripts\python.exe -m scripts.reader_simulator --device-id <UUID> --card-uid <UID> --tap-key <UUID> --journal .benchmark/reader.sqlite
# Reuse the same tap key/journal to exercise recovery; no second pulse is generated.
# --fail-activation simulates a definitive failure before a pulse.
```

The simulator uses SQLite `synchronous=FULL` and a committed execution marker. Unit
tests simulate a power loss between the pulse and final journal update. It is a
protocol reference, not production firmware or proof of hardware durability.
Firmware must verify flash/filesystem behavior, clock discipline, relay pulse
semantics, reboot recovery, connectivity loss, and outcome acknowledgements on the
actual reader and machine. Missing hardware evidence remains an explicit pilot gate.

## Offline boundary

Machine authorization requires connectivity. Do not activate a machine on a failed
authorization request. Offline upload/review recovery is available for existing
legacy readers, with policy row serialization, atomic ledger/status commits,
payload hash validation, venue-currency limits, bounded exposure, and audited sequence conflicts.
Old pending rows with an already-posted matching transaction are completed on
retry without another debit. Pending operations are visible in operational alerts.

Offline machine activation and paid/bonus allocation need a separate signed policy
and firmware contract before enablement. Keep the tenant offline policy disabled
for the initial arcade pilot. Recovery tests do not authorize enabling offline
spending or make cloned card UIDs a secure identity mechanism.
