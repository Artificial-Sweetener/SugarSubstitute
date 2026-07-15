#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Own startup logging policy and lightweight event pumping helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from substitute.app.bootstrap.startup_trace import configure_startup_trace, trace_mark
from substitute.shared.logging.logger import (
    configure_file_logging,
    configure_prompt_observability_logging,
    get_logger,
    log_info,
)

PROMPT_OBSERVABILITY_ENV = "SUGAR_SUBSTITUTE_PROMPT_OBSERVABILITY"
_LOGGER = get_logger("app.bootstrap.startup_logging")


@dataclass(frozen=True)
class StartupObservabilityPaths:
    """Describe startup-owned logging and trace file destinations."""

    log_path: Path
    prompt_observability_log_path: Path | None
    trace_path: Path


def prompt_observability_enabled() -> bool:
    """Return whether durable prompt-editor debug logging was explicitly enabled."""

    value = os.environ.get(PROMPT_OBSERVABILITY_ENV, "")
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def configure_startup_observability(logs_dir: Path) -> StartupObservabilityPaths:
    """Configure startup log files, optional prompt logs, and trace output."""

    log_path = configure_file_logging(logs_dir)
    prompt_observability_log_path = (
        configure_prompt_observability_logging(logs_dir)
        if prompt_observability_enabled()
        else None
    )
    log_info(
        _LOGGER,
        "Runtime file logging initialized",
        log_path=str(log_path),
        prompt_observability_log_path=""
        if prompt_observability_log_path is None
        else str(prompt_observability_log_path),
    )
    trace_path = configure_startup_trace(logs_dir)
    trace_mark(
        "startup.trace.ready",
        trace_path=trace_path,
        log_path=log_path,
    )
    return StartupObservabilityPaths(
        log_path=log_path,
        prompt_observability_log_path=prompt_observability_log_path,
        trace_path=trace_path,
    )


def process_startup_events(app: Any) -> None:
    """Let Qt service pending splash paint/input events before heavy startup work."""

    process_events = getattr(app, "processEvents", None)
    if callable(process_events):
        process_events()


__all__ = [
    "PROMPT_OBSERVABILITY_ENV",
    "StartupObservabilityPaths",
    "configure_startup_observability",
    "process_startup_events",
    "prompt_observability_enabled",
]
