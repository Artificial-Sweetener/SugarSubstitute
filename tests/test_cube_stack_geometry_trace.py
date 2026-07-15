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

"""Tests for opt-in cube-stack geometry trace logging."""

from __future__ import annotations

import logging

import pytest

from substitute.presentation.workflows.cube_stack_geometry_trace import (
    log_cube_item_icon_paint,
    log_cube_stack_transition_frame,
)


class _ExplodingGeometryWidget:
    """Raise if geometry details are read while tracing is disabled."""

    def mapToGlobal(self, _point: object) -> object:
        """Raise when trace context unexpectedly asks for global geometry."""

        raise AssertionError("geometry context should not be built")


def test_geometry_trace_skips_context_when_debug_logging_is_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Normal info-level logging should not build cube-stack trace payloads."""

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.workflows.cube_stack_geometry_trace",
    )
    widget = _ExplodingGeometryWidget()

    log_cube_item_icon_paint(item=widget, icon_x=1, icon_y=2, icon_size=16)
    log_cube_stack_transition_frame(
        stack=widget,
        stack_width=100,
        item_width=80,
        compact_progress=0.5,
    )

    assert caplog.text == ""
