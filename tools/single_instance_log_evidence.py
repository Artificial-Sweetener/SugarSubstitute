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

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


def audit_launcher_log(layout: InstallLayout) -> dict[str, object]:
    """Prove lifecycle diagnostics are present once rather than duplicated."""

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
    required_events = (
        "Elected application supervisor through native IPC",
        "Forwarding secondary invocation",
        "Registered supervised application child",
        "Secondary invocation produced a visible surface",
        "Supervised application child disconnected",
    )
    event_counts = {
        event: sum(event in line for line in lines) for event in required_events
    }
    missing = [event for event, count in event_counts.items() if count == 0]
    if missing:
        raise AssertionError(f"Launcher diagnostics omit lifecycle events: {missing}")
    if any(" process=" not in line for line in lines):
        raise AssertionError("Launcher diagnostics omit process identity.")
    return {
        "line_count": len(lines),
        "adjacent_duplicate_lines": [],
        "event_counts": event_counts,
        "process_identity_on_every_line": True,
    }


__all__ = ["audit_launcher_log"]
