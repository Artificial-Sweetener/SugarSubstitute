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

"""Enforce direct ownership of diagnostic fragment-cache policy."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_diagnostic_owner_receives_cache_operations_without_surface_shims() -> None:
    """Keep cache invalidation, preservation, and observability with its owner."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    publication_source = (projection_root / "edit_publication.py").read_text(
        encoding="utf-8"
    )
    owner_source = (projection_root / "diagnostic_layer_owner.py").read_text(
        encoding="utf-8"
    )

    obsolete_surface_methods = (
        "def _clear_diagnostic_fragment_cache(",
        "def _preserve_diagnostic_fragment_cache_for_incremental_edit(",
    )
    assert all(method not in surface_source for method in obsolete_surface_methods)
    assert "diagnostics: PromptDiagnosticLayerOwner" in publication_source
    assert "self._diagnostics.clear_fragment_cache(" in publication_source
    assert (
        "self._diagnostics.preserve_fragment_cache_for_incremental_edit("
        in publication_source
    )
    assert "PromptEditorWorkEvent.DIAGNOSTIC_CACHE_CLEAR" in owner_source
    assert "PromptEditorWorkEvent.DIAGNOSTIC_CACHE_PRESERVE" in owner_source
