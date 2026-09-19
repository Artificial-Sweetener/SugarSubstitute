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

"""Audit diagnostic evidence produced by instance-lifecycle qualification."""

from __future__ import annotations

from collections.abc import Sequence
import re

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


_LOG_RECORD_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} ")
_INSTALLED_APPLICATION_EVENTS = (
    "Elected application supervisor through native IPC",
    "Forwarding secondary invocation",
    "Queued secondary invocation until a surface owner is available",
    "Registered supervised application child",
    "Secondary invocation produced a visible surface",
    "Supervised application child disconnected",
    "Application supervisor shutdown completed",
)


def audit_launcher_log(
    layout: InstallLayout,
    *,
    required_events: Sequence[str] = _INSTALLED_APPLICATION_EVENTS,
) -> dict[str, object]:
    """Prove scenario diagnostics are identified, complete, and unduplicated."""

    log_path = layout.logs_dir / "launcher.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    adjacent_duplicates = [
        index
        for index, (previous, current) in enumerate(zip(lines, lines[1:]), start=2)
        if previous == current
    ]
    if adjacent_duplicates:
        raise AssertionError(
            "Launcher diagnostics contain duplicate handler output at lines "
            f"{adjacent_duplicates[:8]}."
        )
    event_counts = {
        event: sum(event in line for line in lines) for event in required_events
    }
    missing = [event for event, count in event_counts.items() if count == 0]
    if missing:
        raise AssertionError(f"Launcher diagnostics omit lifecycle events: {missing}")
    record_lines = [line for line in lines if _LOG_RECORD_PREFIX.match(line)]
    if lines and not record_lines:
        raise AssertionError("Launcher diagnostics contain no structured records.")
    first_record_index = next(
        (index for index, line in enumerate(lines) if _LOG_RECORD_PREFIX.match(line)),
        len(lines),
    )
    if any(line.strip() for line in lines[:first_record_index]):
        raise AssertionError(
            "Launcher diagnostics begin with orphaned continuation text."
        )
    if any(" process=" not in line for line in record_lines):
        raise AssertionError("Launcher diagnostics omit process identity.")
    return {
        "line_count": len(lines),
        "record_count": len(record_lines),
        "continuation_line_count": len(lines) - len(record_lines),
        "adjacent_duplicate_lines": [],
        "event_counts": event_counts,
        "process_identity_on_every_record": True,
    }


__all__ = ["audit_launcher_log"]
