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

"""Verify generation preview preference policy."""

from __future__ import annotations

from substitute.domain.generation import (
    GenerationPreviewMethod,
    default_generation_preview_preferences,
)


def test_generation_preview_defaults_resolve_to_latent2rgb() -> None:
    """Enable latent-RGB previews by default."""

    preferences = default_generation_preview_preferences()

    assert preferences.enabled is True
    assert preferences.method is GenerationPreviewMethod.LATENT2RGB
    assert preferences.resolved_comfy_preview_method() == "latent2rgb"


def test_generation_preview_disabled_resolves_to_none() -> None:
    """Use Comfy's no-preview value when previews are disabled."""

    preferences = default_generation_preview_preferences().with_enabled(False)

    assert preferences.resolved_comfy_preview_method() == "none"
