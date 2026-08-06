# ClaimGuard SRE 87 Digital Twin

This module is a public, synthetic implementation of the SRE 87 control-cycle contract. It contains no employer data, credentials, internal URLs, proprietary payloads, or protected health information.

## Preserved operational controls

1. Every run is an independent control cycle.
2. Previous-run claim IDs are checked before new stuck claims are queried.
3. Any prior claim not in status `300` halts the current run with exit code `1`.
4. Eligible claims are older than two hours and in status `655`, `665`, `800`, or `850`.
5. Status routing is deterministic:
   - `655`, `665`, and optionally `660`: CDR Persistence, bulk JSON request.
   - `800`: State Manager, one request per claim.
   - `850`: CBO reprocessor, one JSON request per claim.
6. No same-cycle retry loop is implemented.
7. CSV, JSON, and text logs are written for every cycle.
8. Mock incidents are written once per failed cycle.
9. Operators can pause and resume the automation.
10. Exit codes preserve the BOT/script contract: `0`, `1`, `2`, and `3`.

## Safe demonstration modes

```bash
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 run
```

The happy scenario resolves every eligible claim to status `300`.

```bash
uv run claimguard-sre87 seed --scenario unresolved
uv run claimguard-sre87 run
uv run claimguard-sre87 run
```

The first run submits recovery actions but leaves one claim unresolved. The second run detects that prior claim before querying new work, writes a mock incident, and exits `1`.

```bash
uv run claimguard-sre87 seed --scenario endpoint-failure
uv run claimguard-sre87 run
```

The endpoint-failure scenario produces mock HTTP `503` results, performs no retries, writes one mock incident, and exits `2`.

## Dry run

```bash
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 run --dry-run
```

Dry-run mode calculates routing and payload modes without executing a mock endpoint or recording submitted IDs for next-cycle validation.

## Pause and resume

```bash
uv run claimguard-sre87 pause
uv run claimguard-sre87 run
uv run claimguard-sre87 resume
```

## Generated output

```text
runtime/sre87/
├── incidents/incidents.jsonl
├── logs/YYYY-MM-DD/run_<timestamp>.csv
├── logs/YYYY-MM-DD/run_<timestamp>.json
├── logs/YYYY-MM-DD/run_<timestamp>.log
└── state/last_run.json
```

## Status 660

The reference material contains an ambiguity: status `660` appears in the SQL filter and persistence routing, but not consistently in the four-status eligibility statement. The demo therefore supports routing `660` to Persistence while leaving it disabled by default. Enable it only after the EDI SME confirms the requirement:

```json
"include_status_660": true
```

## Enterprise adapter boundary

The following public-demo classes are explicit replacement points:

- `JsonClaimRepository` → Oracle repository using approved views and runtime credentials.
- `MockRecoveryClient` → authenticated HTTP adapters for the approved reprocessors.
- `MockIncidentService` → ServiceNow integration owned by the BOT or enterprise incident service.

The deterministic routing and prior-run control gate should remain unchanged when enterprise adapters are introduced.
