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

"""Test interaction geometry refresh coordination."""

from __future__ import annotations


from tests.presentation.editor.prompt_editor.interactions.support.reorder_overlay import (
    OverlayDouble,
    OverlayFactoryDouble,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
)

from tests.presentation.editor.prompt_editor.interactions.state.editor_double import (
    StateEditorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.state.support import (
    build_controller,
)


def test_handle_resize_and_scroll_refresh_syntax_renderer_geometry() -> None:
    """Resize, move, and scroll updates request renderer geometry recomputation."""

    syntax_renderers = syntax_renderer_double()
    overlay = OverlayDouble([0], has_reordered=False)
    controller = build_controller(
        StateEditorDouble(text="(cat:1.05)", position=3),
        syntax_renderers=syntax_renderers,
        reorder_overlay_factory=OverlayFactoryDouble(overlay),
    )
    controller.enter_segment_reorder_mode_from_keymap()
    initial_refresh_calls = syntax_renderers.refresh_geometry_calls

    controller.handle_resize()
    controller.handle_move()
    controller.handle_viewport_scroll()

    assert syntax_renderers.refresh_geometry_calls == initial_refresh_calls + 3
    assert overlay.refresh_geometry_calls == 2
