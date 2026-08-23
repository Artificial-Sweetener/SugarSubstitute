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

"""Exercise mounted Input tool-option runtime boundaries."""

from __future__ import annotations

from typing import Any, cast

from cutecanvas import ExecutionRuntime
import pytest

from substitute.presentation.canvas.shared.canvas_top_bar import CanvasTopBar


from tests.presentation.canvas.input.input_tool_options_harness import (
    _mounted_input,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_mounted_input_defers_unrelated_sam_runtime(
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep Input chrome tests independent of native model preparation."""

    canvas, _controller = _mounted_input(monkeypatch, execution_runtime)
    try:
        assert cast(Any, canvas.canvas).samManager() is None
    finally:
        destroy_qt_object(canvas)


def test_top_bar_cannot_observe_its_own_layout_lifecycle() -> None:
    """Keep self-generated layout requests outside the top-bar input surface."""

    assert "event" not in CanvasTopBar.__dict__
