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

"""Build representative Output navigation-bar projection items."""

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
)
from substitute.domain.workflow import ImageMeta


def build_bar_image_item(
    *,
    width: int | None,
    height: int | None,
    duration_ms: float | None,
    set_index: int,
) -> OutputCanvasImageItem:
    """Return a projection item with tooltip-relevant metadata."""

    return OutputCanvasImageItem(
        uuid4(),
        ImageMeta(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=set_index,
            suffix="",
            path=f"C:\\outputs\\image-{set_index}.png",
            width=width,
            height=height,
            list_index=set_index - 1,
            cube_execution_duration_ms=duration_ms,
        ),
        set_index,
    )
