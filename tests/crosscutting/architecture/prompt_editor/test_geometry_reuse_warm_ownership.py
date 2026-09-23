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

"""Enforce focused ownership of projection geometry reuse warming."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_geometry_reuse_warming_to_focused_owner() -> None:
    """Keep deferred memoization scheduling outside the mounted surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    owner_source = (projection_root / "geometry_reuse_warmer.py").read_text(
        encoding="utf-8"
    )
    commit_source = (
        projection_root / "source_document_commit_application.py"
    ).read_text(encoding="utf-8")

    assert "_projection_geometry_reuse_warm_timer" not in surface_source
    assert "def _schedule_projection_geometry_reuse_warm(" not in surface_source
    assert "def _warm_projection_geometry_reuse_indexes(" not in surface_source
    assert "class PromptProjectionGeometryReuseWarmer" in owner_source
    assert "self._schedule_geometry_reuse_warm(" in commit_source
