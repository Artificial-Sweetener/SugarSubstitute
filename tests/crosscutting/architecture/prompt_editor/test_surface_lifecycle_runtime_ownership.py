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
    assert "build_prompt_projection_surface_lifecycle_runtime(" in surface_source


def test_lifecycle_composes_after_source_freshness_is_available() -> None:
    """Prevent lifecycle owners from closing over a future freshness owner."""

    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )

    source_state_index = surface_source.index(
        "source_state_owners = build_prompt_projection_source_state_owners("
    )
    freshness_index = surface_source.index(
        "self._projection_freshness_controller = source_state_owners.freshness_controller"
    )
    lifecycle_index = surface_source.index(
        "lifecycle_runtime = build_prompt_projection_surface_lifecycle_runtime("
    )
    assert source_state_index < freshness_index < lifecycle_index


def test_source_state_uses_an_explicit_late_bound_effect_port() -> None:
    """Keep source composition independent of future surface-owned runtimes."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    source_wiring_source = (projection_root / "source_state_wiring.py").read_text(
        encoding="utf-8"
    )
    source_block_start = surface_source.index(
        "source_state_owners = build_prompt_projection_source_state_owners("
    )
    source_block_end = surface_source.index(
        "self._source_document_adapter =", source_block_start
    )
    source_block = surface_source[source_block_start:source_block_end]

    assert "lifecycle_effects=source_lifecycle_effects" in source_block
    assert "self._presentation_runtime" not in source_block
    assert "self._caret_visual_controller" not in source_block
    assert "self._reorder" not in source_block
    assert "bindings.lifecycle_effects" in source_wiring_source

    presentation_index = surface_source.index("self._presentation_runtime =")
    effect_binding_index = surface_source.index(
        "bind_prompt_projection_source_lifecycle_effects("
    )
    assert presentation_index < effect_binding_index


def test_pre_source_owners_use_an_explicit_graph_effect_port() -> None:
    """Prevent early owner construction from closing over future surface fields."""

    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    graph_start = surface_source.index(
        "graph_effects = PromptProjectionSurfaceGraphEffects()"
    )
    graph_end = surface_source.index(
        "source_lifecycle_effects = PromptProjectionSourceLifecycleEffects()"
    )
    graph_block = surface_source[graph_start:graph_end]

    assert "self._presentation_runtime." not in graph_block
    assert "self._projection_freshness_controller." not in graph_block
    assert "self._caret_visual_controller." not in graph_block
    assert "graph_effects.rebuild_projection" in graph_block
    assert "graph_effects.ensure_caret_visible" in graph_block

    presentation_index = surface_source.index("self._presentation_runtime =")
    effect_binding_index = surface_source.index(
        "bind_prompt_projection_surface_graph_effects("
    )
    assert presentation_index < effect_binding_index
