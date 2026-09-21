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

"""Enforce focused ownership of reorder projection-paint caches."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_reorder_paint_cache_state_to_focused_owner() -> None:
    """Keep snapshot identity, reuse, counters, and retained entries together."""
    owner_source = (
        PROMPT_PRESENTATION_ROOT
        / "projection"
        / "reorder_paint_snapshot_cache_owner.py"
    ).read_text(encoding="utf-8")
    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    projection_owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_projection_owner.py"
    ).read_text(encoding="utf-8")

    for ownership_marker in (
        "PromptReorderProjectionSnapshotKey(",
        "reuse_reorder_paint_snapshots(",
        "_preview_snapshots_by_index",
        "_live_snapshots_by_index",
        "_exact_reuse_count",
        "_scroll_reuse_count",
        "_rebuild_count",
    ):
        assert ownership_marker in owner_source
        assert ownership_marker not in surface_source
    assert "PromptReorderPaintSnapshotCacheOwner(" in projection_owner_source
    assert "PromptReorderPaintSnapshotCacheOwner(" not in surface_source


def test_surface_exposes_one_reorder_owner_without_reorder_forwarding_shims() -> None:
    """Keep reorder projection authority out of the mounted editing surface."""

    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    lifecycle_runtime_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface_lifecycle_runtime.py"
    ).read_text(encoding="utf-8")

    assert "self._reorder = lifecycle_runtime.reorder" in surface_source
    assert "PromptReorderProjectionOwner(" in lifecycle_runtime_source
    assert "PromptReorderProjectionOwner(" not in surface_source
    for forbidden_marker in (
        "self._reorder_preview_projection",
        "self._reorder_geometry_owner",
        "self._reorder_paint_snapshots",
        "self._reorder_surface_visual_state",
        "def set_reorder_preview_state(",
        "def reorder_preview_fragments(",
        "def reorder_placement_at_rect(",
        "def set_reorder_surface_visual_publication(",
    ):
        assert forbidden_marker not in surface_source
