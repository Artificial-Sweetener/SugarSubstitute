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

"""Enforce focused ownership of source-ready projection lifecycle composition."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_source_ready_lifecycle_construction() -> None:
    """Keep the lifecycle collaborator graph out of the mounted Qt surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    runtime_source = (projection_root / "surface_lifecycle_runtime.py").read_text(
        encoding="utf-8"
    )
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )

    for construction_marker in (
        "PromptProjectionLayoutWidthResolver(",
        "PromptReorderProjectionOwner(",
        "PromptProjectionSelectionLayerOwner(",
        "PromptSurfaceCaretVisualController(",
        "PromptProjectionEmphasisOwner(",
        "PromptProjectionCaretMovementController(",
    ):
        assert construction_marker in runtime_source
        assert construction_marker not in surface_source
    assert "build_prompt_projection_surface_lifecycle_runtime(" in composition_source
    assert "build_prompt_projection_surface_lifecycle_runtime(" not in surface_source
    assert "build_prompt_projection_surface_composition_runtime(" in surface_source


def test_lifecycle_composes_after_source_freshness_is_available() -> None:
    """Prevent lifecycle owners from closing over a future freshness owner."""

    composition_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_composition_runtime.py"
    ).read_text(encoding="utf-8")

    source_state_index = composition_source.index(
        "source = build_prompt_projection_source_state_owners("
    )
    lifecycle_index = composition_source.index(
        "lifecycle = build_prompt_projection_surface_lifecycle_runtime("
    )
    lifecycle_block_end = composition_source.index(
        "presentation = build_prompt_projection_surface_presentation_runtime("
    )
    lifecycle_block = composition_source[lifecycle_index:lifecycle_block_end]

    assert source_state_index < lifecycle_index
    assert "freshness=source.freshness_controller" in lifecycle_block


def test_source_state_uses_an_explicit_late_bound_effect_port() -> None:
    """Keep source composition independent of future surface-owned runtimes."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )
    source_wiring_source = (projection_root / "source_state_wiring.py").read_text(
        encoding="utf-8"
    )
    source_block_start = composition_source.index(
        "source = build_prompt_projection_source_state_owners("
    )
    source_block_end = composition_source.index(
        "lifecycle = build_prompt_projection_surface_lifecycle_runtime(",
        source_block_start,
    )
    source_block = composition_source[source_block_start:source_block_end]

    assert "lifecycle_effects=source_lifecycle_effects" in source_block
    assert "presentation." not in source_block
    assert "lifecycle." not in source_block
    assert "bindings.lifecycle_effects" in source_wiring_source
    assert "bind_prompt_projection_source_lifecycle_effects(" not in surface_source

    presentation_index = composition_source.index(
        "presentation = build_prompt_projection_surface_presentation_runtime("
    )
    effect_binding_index = composition_source.index(
        "bind_prompt_projection_source_lifecycle_effects("
    )
    assert presentation_index < effect_binding_index


def test_pre_source_owners_use_an_explicit_graph_effect_port() -> None:
    """Prevent early owner construction from closing over future surface fields."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )
    interaction_runtime_source = (
        projection_root / "surface_interaction_runtime.py"
    ).read_text(encoding="utf-8")
    source_start = composition_source.index(
        "source = build_prompt_projection_source_state_owners("
    )
    source_end = composition_source.index(
        "lifecycle = build_prompt_projection_surface_lifecycle_runtime(", source_start
    )
    source_block = composition_source[source_start:source_end]

    graph_port_index = surface_source.index(
        "graph_effects = PromptProjectionSurfaceGraphEffects()"
    )
    interaction_index = surface_source.index(
        "interaction_runtime = build_prompt_projection_surface_interaction_runtime("
    )
    composition_index = surface_source.index(
        "composition_runtime = build_prompt_projection_surface_composition_runtime("
    )
    assert graph_port_index < interaction_index < composition_index
    assert "presentation." not in source_block
    assert "lifecycle." not in source_block
    assert "graph_effects=graph_effects" in surface_source
    assert "graph_effects=bindings.graph_effects" not in source_block
    assert "graph_effects.rebuild_projection" in interaction_runtime_source
    assert "graph_effects.ensure_caret_visible" in interaction_runtime_source
    assert "bind_prompt_projection_surface_graph_effects(" not in surface_source

    presentation_index = composition_source.index(
        "presentation = build_prompt_projection_surface_presentation_runtime("
    )
    effect_binding_index = composition_source.index(
        "bind_prompt_projection_surface_graph_effects("
    )
    assert presentation_index < effect_binding_index
