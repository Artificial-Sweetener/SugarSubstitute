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

"""Enforce focused ownership of prompt fill-band presentation."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_projection_surface_delegates_complete_fill_band_publication() -> None:
    """Keep cache identity, freshness selection, and geometry outside the surface."""

    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "fill_band_owner.py"
    ).read_text(encoding="utf-8")
    query_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "presentation_query_owner.py"
    ).read_text(encoding="utf-8")
    runtime_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_presentation_runtime.py"
    ).read_text(encoding="utf-8")

    assert (
        "self._presentation_runtime.queries.visible_fill_band_rects()" in surface_source
    )
    assert "self._presentation_runtime.queries.fill_band_color()" in surface_source
    assert "self._fill_bands.visible_rects()" in query_source
    assert "self._fill_bands.color()" in query_source
    assert "fill_bands = PromptProjectionFillBandOwner(" in runtime_source
    assert "fill_bands=fill_bands" in runtime_source
    assert "PromptProjectionFillBandCacheKey" not in surface_source
    assert "PromptProjectionFillBandBuildRequest" not in surface_source
    assert "_fill_band_cache" not in surface_source
    assert "PromptProjectionFillBandCacheKey" in owner_source
    assert "PromptProjectionFillBandBuildRequest" in owner_source
    assert "PromptProjectionFillBandCache()" in owner_source
