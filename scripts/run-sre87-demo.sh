#!/usr/bin/env bash
set -euo pipefail

scenario="${1:-happy}"

uv run claimguard-sre87 seed --scenario "$scenario"
uv run claimguard-sre87 run
uv run claimguard-sre87 status
