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

"""Share temporary QPane SAM warmup state without crossing app/UI layers."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class QPaneSamWarmupSnapshot:
    """Describe the latest QPane SAM dependency warmup state."""

    state: str
    elapsed_ms: float | None = None
    error: str = ""


_STATE_LOCK = Lock()
_STATE = QPaneSamWarmupSnapshot(state="not_started")


def set_qpane_sam_warmup_snapshot(snapshot: QPaneSamWarmupSnapshot) -> None:
    """Publish one warmup state snapshot."""

    global _STATE
    with _STATE_LOCK:
        _STATE = snapshot


def qpane_sam_warmup_snapshot() -> QPaneSamWarmupSnapshot:
    """Return the latest dependency warmup state for temporary diagnostics."""

    with _STATE_LOCK:
        return _STATE


def reset_qpane_sam_warmup_snapshot_for_tests() -> None:
    """Reset warmup state for focused tests."""

    set_qpane_sam_warmup_snapshot(QPaneSamWarmupSnapshot(state="not_started"))


__all__ = [
    "QPaneSamWarmupSnapshot",
    "qpane_sam_warmup_snapshot",
    "reset_qpane_sam_warmup_snapshot_for_tests",
    "set_qpane_sam_warmup_snapshot",
]
