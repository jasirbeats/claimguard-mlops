from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """BOT/script contract preserved from the SRE 87 SOP."""

    SUCCESS = 0
    PRIOR_RUN_HALT = 1
    RUNTIME_FAILURE = 2
    UNEXPECTED_FAILURE = 3
