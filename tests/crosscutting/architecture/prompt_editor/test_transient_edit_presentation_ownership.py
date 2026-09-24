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

"""Enforce focused ownership of transient edit repaint policy."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_feedback_strategies_publish_through_transient_presentation_owner() -> None:
    """Keep overlay geometry and viewport damage outside the mounted surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    direct_source = (projection_root / "direct_feedback_strategy.py").read_text(
        encoding="utf-8"
    )
    deferred_source = (projection_root / "deferred_feedback_strategy.py").read_text(
        encoding="utf-8"
    )
    owner_source = (projection_root / "transient_edit_presentation_owner.py").read_text(
        encoding="utf-8"
    )

    obsolete_surface_methods = (
        "def _transient_insertion_overlay_viewport_rect(",
        "def _transient_insertion_overlay_document_rect(",
        "def _transient_deletion_overlay_viewport_rects(",
        "def _transient_deletion_overlay_erase_rects(",
        "def _update_transient_insertion_overlay_paint(",
        "def _update_transient_deletion_overlay_paint(",
    )
    assert all(method not in surface_source for method in obsolete_surface_methods)
    assert "self._presentation.update_insertion_overlay_paint(" in direct_source
    assert "self._presentation.update_deletion_overlay_paint(" in direct_source
    assert "self._presentation.update_insertion_overlay_paint(" in deferred_source
    assert "self._presentation.update_deletion_overlay_paint(" in deferred_source
    assert "class PromptTransientEditPresentationOwner" in owner_source
    assert "self._viewport.update(" in owner_source
