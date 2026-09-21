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

"""Enforce single ownership of projection render-frame publication."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_complete_render_publication_to_focused_owner() -> None:
    """Keep paint-mode and frame-input selection out of the mounted Qt surface."""
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "render_publication_owner.py"
    ).read_text(encoding="utf-8")
    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "PromptProjectionContentPaintMode",
        "PromptReorderRenderInstrumentation",
        "_fresh_reorder_surface_chrome",
        "_prepare_source_line_chrome",
        "_prepare_search_highlight",
        "def viewport_scrolled",
        "def layout_synchronized",
        "def caret_changed",
    ):
        assert ownership_marker in owner_source
        assert ownership_marker not in surface_source
    assert "self._render_publication.publish()" in surface_source
    for direct_layer_orchestration in (
        "self._diagnostic_layer_owner.refresh(",
        "self._diagnostic_layer_owner.clear_fragment_cache(",
        "self._selection_layer_owner.refresh()",
        "self._search_highlight_layer.clear()",
        "self._input_method_controller.refresh_render_layer()",
    ):
        assert direct_layer_orchestration not in surface_source


def test_input_method_controller_owns_qt_event_and_focus_lifecycle() -> None:
    """Keep IME sequencing out of the mounted projection surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    owner_source = (projection_root / "input_method_controller.py").read_text(
        encoding="utf-8"
    )
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")

    for ownership_marker in (
        "def dispatch_event(",
        "def focus_out(",
        "QApplication.inputMethod().commit()",
        "QApplication.inputMethod().update(",
        'self._finish_pending_key_edit_block("input_method_event")',
    ):
        assert ownership_marker in owner_source
        assert ownership_marker not in surface_source
    assert "self._input_method_controller.dispatch_event(event)" in surface_source
    assert "self._input_method_controller.focus_out()" in surface_source
