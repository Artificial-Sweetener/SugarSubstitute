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

"""Read terminal events incrementally from packaged qualification journals."""

from __future__ import annotations

from collections.abc import Collection
import json
from pathlib import Path

_TERMINAL_STARTUP_FAILURE_EVENTS = frozenset(
    {
        "startup.gui_task.failure",
        "startup.managed.failure",
    }
)
_TERMINAL_QUALIFICATION_FAILURE_EVENTS = frozenset({"installer.qualification.failed"})


def read_terminal_startup_failure(
    trace_path: Path,
    *,
    offset: int,
) -> tuple[int, str | None]:
    """Return the next terminal application-startup event after an offset."""

    return _read_terminal_event(
        trace_path,
        offset=offset,
        terminal_events=_TERMINAL_STARTUP_FAILURE_EVENTS,
        expected_token=None,
    )


def read_terminal_qualification_failure(
    event_log_path: Path,
    *,
    offset: int,
    token: str,
) -> tuple[int, str | None]:
    """Return the next token-bound terminal installer event after an offset."""

    return _read_terminal_event(
        event_log_path,
        offset=offset,
        terminal_events=_TERMINAL_QUALIFICATION_FAILURE_EVENTS,
        expected_token=token,
    )


def _read_terminal_event(
    path: Path,
    *,
    offset: int,
    terminal_events: Collection[str],
    expected_token: str | None,
) -> tuple[int, str | None]:
    """Advance through complete JSONL records and return one matching event."""

    try:
        with path.open(encoding="utf-8", errors="replace") as journal:
            journal.seek(offset)
            while True:
                line = journal.readline()
                if not line:
                    return journal.tell(), None
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if (
                    expected_token is not None
                    and payload.get("token") != expected_token
                ):
                    continue
                event = payload.get("event")
                if isinstance(event, str) and event in terminal_events:
                    return journal.tell(), event
    except OSError:
        return offset, None


__all__ = [
    "read_terminal_qualification_failure",
    "read_terminal_startup_failure",
]
