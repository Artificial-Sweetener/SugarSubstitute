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

"""Enforce one owner for the late projection-surface collaborator graph."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_late_projection_graph_composition() -> None:
    """Keep source, lifecycle, presentation, and effect wiring together."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "PromptProjectionGeometryReuseWarmer(",
        "PromptProjectionSourceLifecycleEffects()",
        "build_prompt_projection_source_state_owners(",
        "build_prompt_projection_surface_lifecycle_runtime(",
        "build_prompt_projection_surface_presentation_runtime(",
        "bind_prompt_projection_surface_graph_effects(",
        "bind_prompt_projection_source_lifecycle_effects(",
    ):
        assert ownership_marker in composition_source
        assert ownership_marker not in surface_source

    assert "build_prompt_projection_surface_composition_runtime(" in surface_source


def test_composition_binds_effect_ports_after_complete_graph_construction() -> None:
    """Prevent callbacks from observing partially composed projection owners."""

    composition_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_composition_runtime.py"
    ).read_text(encoding="utf-8")

    source_index = composition_source.index(
        "source = build_prompt_projection_source_state_owners("
    )
    lifecycle_index = composition_source.index(
        "lifecycle = build_prompt_projection_surface_lifecycle_runtime("
    )
    presentation_index = composition_source.index(
        "presentation = build_prompt_projection_surface_presentation_runtime("
    )
    graph_binding_index = composition_source.index(
        "bind_prompt_projection_surface_graph_effects("
    )
    source_binding_index = composition_source.index(
        "bind_prompt_projection_source_lifecycle_effects("
    )

    assert (
        source_index
        < lifecycle_index
        < presentation_index
        < graph_binding_index
        < source_binding_index
    )
