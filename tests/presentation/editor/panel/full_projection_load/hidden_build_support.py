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

"""Provide deterministic timer routing for full-projection build tests."""

from __future__ import annotations

from __future__ import annotations
from typing import Any, cast
import pytest
import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.presentation.editor.panel.projection_support import (
    _TimerQueue,
)


def _patch_hidden_build_timer(
    monkeypatch: pytest.MonkeyPatch,
    timer_queue: _TimerQueue,
) -> None:
    """Route hidden-build scheduler timers through a deterministic queue."""

    timer = cast(Any, getattr(hidden_build_scheduler, "QTimer"))
    monkeypatch.setattr(
        timer,
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )
