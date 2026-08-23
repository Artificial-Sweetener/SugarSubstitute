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

"""Verify Output source-tab tooltip text presentation."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_source_tooltip_presenter import (
    source_tab_tooltip_text,
)


def test_source_tab_tooltip_uses_active_set_metadata() -> None:
    """Tooltip text should use the item nearest to the active set."""

    source = OutputCanvasSourceGroup(
        source_key="txt",
        label="Text",
        images_by_set={
            1: _item(width=512, height=512, duration_ms=1.0, set_index=1),
            2: _item(width=1024, height=768, duration_ms=3080.0, set_index=2),
        },
    )

    assert source_tab_tooltip_text(source, active_set_index=2) == "1024x768\n3.1s"


def test_source_tab_tooltip_returns_empty_without_display_metadata() -> None:
    """Sources without size or duration metadata should not show tooltip text."""

    source = OutputCanvasSourceGroup(
        source_key="txt",
        label="Text",
        images_by_set={1: OutputCanvasImageItem(uuid4(), _metadata(), 1)},
    )

    assert source_tab_tooltip_text(source, active_set_index=1) == ""


def test_source_tab_tooltip_keeps_duration_without_size() -> None:
    """Duration metadata should still be shown when size metadata is absent."""

    source = OutputCanvasSourceGroup(
        source_key="txt",
        label="Text",
        images_by_set={1: _item(width=None, height=None, duration_ms=1500.0)},
    )

    assert source_tab_tooltip_text(source, active_set_index=1) == "1.5s"


def test_source_tab_tooltip_keeps_size_without_duration() -> None:
    """Size metadata should still be shown when duration metadata is absent."""

    source = OutputCanvasSourceGroup(
        source_key="txt",
        label="Text",
        images_by_set={1: _item(width=640, height=480, duration_ms=None)},
    )

    assert source_tab_tooltip_text(source, active_set_index=1) == "640x480"


def _item(
    *,
    width: int | None,
    height: int | None,
    duration_ms: float | None,
    set_index: int = 1,
) -> OutputCanvasImageItem:
    """Return one tooltip source item with synthetic metadata."""

    return OutputCanvasImageItem(
        uuid4(),
        _metadata(
            width=width,
            height=height,
            cube_execution_duration_ms=duration_ms,
        ),
        set_index,
    )


def _metadata(
    *,
    width: int | None = None,
    height: int | None = None,
    cube_execution_duration_ms: float | None = None,
) -> ImageMeta:
    """Return typed image metadata for tooltip tests."""

    return ImageMeta(
        "Workflow",
        "Cube",
        1,
        "",
        "E:/outputs/image.png",
        width=width,
        height=height,
        cube_execution_duration_ms=cube_execution_duration_ms,
    )
