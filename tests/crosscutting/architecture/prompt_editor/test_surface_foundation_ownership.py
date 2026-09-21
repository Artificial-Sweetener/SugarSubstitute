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

"""Enforce focused ownership of prompt projection surface foundations."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_source_independent_foundation_construction() -> None:
    """Keep stable state construction out of the lifecycle-dependent Qt surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    foundation_source = (projection_root / "surface_foundation.py").read_text(
        encoding="utf-8"
    )

    for construction_marker in (
        "PromptProjectionApplicator(",
        "PromptProjectionInlineObjectRendererRegistry(",
        "build_initial_prompt_projection_state(",
        "PromptProjectionFrameStatePublisher(",
        "PromptProjectionCaretStateOwner(",
        "PromptProjectionTransientEditOverlayController(",
    ):
        assert construction_marker in foundation_source
        assert construction_marker not in surface_source
    assert "build_prompt_projection_surface_foundation(" in surface_source


def test_lora_features_consume_public_editor_state_contract() -> None:
    """Keep LoRA media behavior independent of the surface's private storage."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    lora_source = (projection_root / "lora_surface_features.py").read_text(
        encoding="utf-8"
    )

    assert "def editor_state(" in lora_source
    assert "self._host.editor_state.projection.document.tokens" in lora_source
    assert "self._host._editor_state" not in lora_source
