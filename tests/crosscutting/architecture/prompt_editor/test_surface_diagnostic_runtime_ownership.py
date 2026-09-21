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

"""Enforce focused ownership of surface diagnostic presentation composition."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_diagnostic_presentation_construction() -> None:
    """Keep diagnostic state and visual binding out of the Qt event surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    runtime_source = (projection_root / "surface_diagnostic_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "PromptDiagnosticLayerOwner(" in runtime_source
    assert "PromptDiagnosticLayerOwner(" not in surface_source
    assert "semantic_palette_from_theme()" in runtime_source
    assert "build_prompt_projection_surface_diagnostics(" in surface_source
