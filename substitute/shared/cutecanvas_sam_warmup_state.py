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

"""Share CuteCanvas SAM dependency readiness without crossing app/UI layers."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class CuteCanvasSamWarmupSnapshot:
    """Describe the latest CuteCanvas SAM dependency warmup state."""

    state: str
    elapsed_ms: float | None = None
    error: str = ""


_STATE_LOCK = Lock()
_STATE = CuteCanvasSamWarmupSnapshot(state="not_started")
_TERMINAL_STATES = frozenset({"completed", "disabled", "failed"})


def set_cutecanvas_sam_warmup_snapshot(snapshot: CuteCanvasSamWarmupSnapshot) -> None:
    """Publish one warmup state snapshot."""

    global _STATE
    with _STATE_LOCK:
        _STATE = snapshot


def cutecanvas_sam_warmup_snapshot() -> CuteCanvasSamWarmupSnapshot:
    """Return the latest dependency warmup state."""

    with _STATE_LOCK:
        return _STATE


def cutecanvas_sam_warmup_is_terminal() -> bool:
    """Return whether dependency import work can no longer compete with the GUI."""

    return cutecanvas_sam_warmup_snapshot().state in _TERMINAL_STATES


def reset_cutecanvas_sam_warmup_snapshot_for_tests() -> None:
    """Reset warmup state for focused tests."""

    set_cutecanvas_sam_warmup_snapshot(CuteCanvasSamWarmupSnapshot(state="not_started"))


__all__ = [
    "CuteCanvasSamWarmupSnapshot",
    "cutecanvas_sam_warmup_is_terminal",
    "cutecanvas_sam_warmup_snapshot",
    "reset_cutecanvas_sam_warmup_snapshot_for_tests",
    "set_cutecanvas_sam_warmup_snapshot",
]
