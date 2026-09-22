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

"""Enforce focused composition of projection-surface input controllers."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_complete_source_input_runtime_construction() -> None:
    """Keep input-controller graph construction out of the mounted Qt surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    runtime_source = (projection_root / "surface_input_runtime.py").read_text(
        encoding="utf-8"
    )
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )

    for construction_marker in (
        "PromptInputMethodController(",
        "PromptSurfaceDeletionController(",
        "PromptSurfaceKeyHandler(",
        "PromptSurfaceWheelHandler(",
        "PromptExternalTextInputOwner(",
        "PromptProjectionViewportEventRouter(",
        "PromptProjectionHistoryOwner(",
    ):
        assert construction_marker in runtime_source
        assert construction_marker not in surface_source
    assert "build_prompt_projection_surface_input_runtime(" in composition_source
    assert "build_prompt_projection_surface_input_runtime(" not in surface_source
    assert "build_prompt_projection_surface_composition_runtime(" in surface_source


def test_source_state_composes_after_initialized_input_runtime() -> None:
    """Prevent source publication from closing over a future IME controller."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    composition_source = (projection_root / "surface_composition_runtime.py").read_text(
        encoding="utf-8"
    )

    input_runtime_index = composition_source.index(
        "input_runtime = build_prompt_projection_surface_input_runtime("
    )
    source_state_index = composition_source.index(
        "source = build_prompt_projection_source_state_owners("
    )
    source_state_end = composition_source.index(
        "lifecycle = build_prompt_projection_surface_lifecycle_runtime("
    )
    source_state_block = composition_source[source_state_index:source_state_end]

    assert "build_prompt_projection_surface_composition_runtime(" in surface_source
    assert input_runtime_index < source_state_index
    assert "input_method_source_changed=input_runtime.input_method.source_changed" in (
        source_state_block
    )
