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
    ):
        assert ownership_marker in owner_source
        assert ownership_marker not in surface_source
    assert "self._render_publication.publish()" in surface_source
