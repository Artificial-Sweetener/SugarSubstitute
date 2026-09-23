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

"""Verify event-driven publication of prompt projection render layers."""

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


def test_search_changes_publish_the_exact_prepared_layer(
    widgets: list[QWidget],
) -> None:
    """Keep search session, prepared commands, and render frame atomic."""

    box = show_prompt_editor(widgets, text="alpha beta alpha", width=360)
    surface = surface_for(box)

    surface.set_search_matches(((0, 5), (11, 5)), active_index=1)

    prepared_layer = cast(Any, surface)._search_highlight_layer.layer
    published_frame = cast(Any, surface)._presentation_runtime.render_frame.frame
    assert published_frame.search_layer is prepared_layer
    assert len(published_frame.search_layer.rects) == 2
    assert published_frame.search_layer.key is not None
    assert published_frame.search_layer.key.active_match_index == 1

    surface.clear_search_matches()

    cleared_layer = cast(Any, surface)._search_highlight_layer.layer
    cleared_frame = cast(Any, surface)._presentation_runtime.render_frame.frame
    assert cleared_frame.search_layer is cleared_layer
    assert cleared_frame.search_layer.rects == ()


def test_source_line_enablement_publishes_the_prepared_layer_atomically(
    widgets: list[QWidget],
) -> None:
    """Expose newly enabled source-line chrome in the next render frame."""

    box = show_prompt_editor(widgets, text="alpha\nbeta", width=360)
    surface = surface_for(box)

    surface.set_source_line_chrome_enabled(True)

    prepared_layer = cast(Any, surface)._source_line_chrome.layer
    published_frame = cast(Any, surface)._presentation_runtime.render_frame.frame
    assert prepared_layer.key is not None
    assert prepared_layer.fills
    assert published_frame.source_line_layer is prepared_layer

    surface.set_source_line_chrome_enabled(False)

    cleared_layer = cast(Any, surface)._source_line_chrome.layer
    cleared_frame = cast(Any, surface)._presentation_runtime.render_frame.frame
    assert cleared_layer.key is None
    assert cleared_layer.fills == ()
    assert cleared_frame.source_line_layer is cleared_layer


def test_caret_change_republishes_source_line_focus_geometry(
    widgets: list[QWidget],
) -> None:
    """Keep the highlighted source line synchronized with the source caret."""

    box = show_prompt_editor(widgets, text="alpha\nbeta", width=360)
    surface = surface_for(box)
    surface.set_cursor_positions(cursor_position=0, anchor_position=0)
    surface.set_source_line_chrome_enabled(True)
    initial_layer = cast(
        Any, surface
    )._presentation_runtime.render_frame.frame.source_line_layer

    surface.set_cursor_positions(cursor_position=6, anchor_position=6)

    published_frame = cast(Any, surface)._presentation_runtime.render_frame.frame
    prepared_layer = cast(Any, surface)._source_line_chrome.layer
    assert published_frame.source_line_layer is prepared_layer
    assert published_frame.source_line_layer is not initial_layer
    assert published_frame.source_line_layer.key is not None
    assert published_frame.source_line_layer.key.current_line_index == 1
