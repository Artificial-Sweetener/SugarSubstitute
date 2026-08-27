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

"""Verify prompt projection render-frame publication reuse."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_unchanged_render_publication_reuses_exact_frame(
    widgets: list[QWidget],
) -> None:
    """Reuse the same immutable frame when publication inputs are unchanged."""

    box = show_prompt_editor(widgets, text="alpha beta", width=360)
    surface = surface_for(box)
    owner = cast(Any, surface)._render_frame_owner
    initial_frame = owner.frame

    cast(Any, surface)._publish_render_frame()
    first_repeat = owner.frame
    cast(Any, surface)._publish_render_frame()

    assert first_repeat is initial_frame
    assert owner.frame is initial_frame
