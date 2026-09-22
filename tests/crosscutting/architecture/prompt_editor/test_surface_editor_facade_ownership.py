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

"""Enforce focused ownership of the mounted projection editor API."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_editor_facade_owns_source_and_projection_query_behavior() -> None:
    """Keep semantic editor behavior out of the Qt event adapter."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    facade_source = (projection_root / "surface_editor_facade.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "source_document.document()",
        "return self._bindings.editing_session.source_text",
        "presentation.queries.projection_document",
        "presentation.queries.active_projection_document",
        "presentation.queries.source_range_fragments(",
        "presentation.search.set_matches(",
        "presentation.scene_diagnostics.set_keys(",
        "source_commit.apply_edit_commit(",
    ):
        assert ownership_marker in facade_source
        assert ownership_marker not in surface_source

    assert "self._editor_facade = composition_runtime.editor" in surface_source


def test_key_handler_consumes_editor_state_through_its_host_contract() -> None:
    """Prevent key routing from reaching into surface-owned private state."""

    keymap_source = (PROMPT_PRESENTATION_ROOT / "interactions" / "keymap.py").read_text(
        encoding="utf-8"
    )

    assert "def editing_enabled(self) -> bool:" in keymap_source
    assert "host.editing_enabled()" in keymap_source
    assert "host._editing_enabled" not in keymap_source
