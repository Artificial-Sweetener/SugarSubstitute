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

"""Verify durable installer interaction and startup-handoff evidence."""

from __future__ import annotations

import json
from pathlib import Path

from tools.ci.installer_lifecycle_errors import InstallerLifecycleError

_SHELL_FRAME_PAINT_EVENT = "main_shell.first_paint"
_REQUIRED_STARTUP_EVENTS = (
    "launch_splash.started",
    "main_shell.shown",
    _SHELL_FRAME_PAINT_EVENT,
    "launch_splash.closed",
)


def assert_qualification_event_sequence(
    event_log_path: Path,
    *,
    token: str,
    required_events: tuple[str, ...],
) -> None:
    """Require token-bound production UI interactions in their expected order."""

    try:
        lines = event_log_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError as error:
        raise InstallerLifecycleError(
            f"Installer did not write its UI qualification log: {event_log_path}."
        ) from error
    events: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise InstallerLifecycleError(
                f"Installer wrote malformed UI qualification JSON: {event_log_path}."
            ) from error
        if not isinstance(payload, dict) or payload.get("token") != token:
            raise InstallerLifecycleError(
                "Installer UI qualification evidence did not match this CI run."
            )
        event = payload.get("event")
        if isinstance(event, str):
            events.append(event)
    if not _contains_ordered_events(events, required_events):
        raise InstallerLifecycleError(
            "Installer UI did not complete the required interaction sequence: "
            + " -> ".join(required_events)
            + ".\n"
            + diagnostic_tail(event_log_path)
        )


def assert_startup_trace_sequence(trace_path: Path) -> None:
    """Require the splash to remain until its replacement shell has painted."""

    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        raise InstallerLifecycleError(
            f"Button-launched child did not write its startup trace: {trace_path}."
        ) from error
    events: list[str] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise InstallerLifecycleError(
                f"Button-launched child wrote malformed startup trace JSON: {trace_path}."
            ) from error
        if isinstance(payload, dict) and isinstance(payload.get("event"), str):
            events.append(payload["event"])
            if _is_shell_frame_paint(payload):
                events.append(_SHELL_FRAME_PAINT_EVENT)
    if not _contains_ordered_events(events, _REQUIRED_STARTUP_EVENTS):
        raise InstallerLifecycleError(
            "Open Substitute did not complete the required splash-to-shell sequence: "
            + " -> ".join(_REQUIRED_STARTUP_EVENTS)
            + ".\n"
            + diagnostic_tail(trace_path)
        )


def diagnostic_tail(path: Path, *, maximum_lines: int = 80) -> str:
    """Return a bounded diagnostic suffix when a qualification step fails."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"<missing diagnostics: {path}>"
    return "\n".join(lines[-maximum_lines:])


def _is_shell_frame_paint(payload: object) -> bool:
    """Return whether one trace record proves the replacement shell painted."""

    if not isinstance(payload, dict):
        return False
    if payload.get("event") != "startup.visibility.first_event":
        return False
    fields = payload.get("fields")
    return (
        isinstance(fields, dict)
        and fields.get("label") == "shell_frame"
        and fields.get("event_type") == "Paint"
    )


def _contains_ordered_events(
    events: list[str],
    required_events: tuple[str, ...],
) -> bool:
    """Return whether every required event appears in order."""

    if not required_events:
        return True
    next_index = 0
    for event in events:
        if event == required_events[next_index]:
            next_index += 1
            if next_index == len(required_events):
                return True
    return False


__all__ = [
    "assert_qualification_event_sequence",
    "assert_startup_trace_sequence",
    "diagnostic_tail",
]
