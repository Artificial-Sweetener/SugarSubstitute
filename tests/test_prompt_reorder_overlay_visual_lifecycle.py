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

"""Verify focused cold-path reorder overlay visual lifecycle ownership."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from PySide6.QtGui import QColor
import pytest

from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureStateView,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_visual_owner import (
    PromptReorderLiveVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_overlay_visual_lifecycle import (
    PromptReorderOverlayVisualLifecycleOwner,
    PromptReorderThemeRefreshRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_publication import (
    PromptReorderRasterPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_refresh_identity import (
    PromptReorderRefreshIdentityOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    PromptReorderVisualStyle,
)


@dataclass
class _AnimationDouble:
    """Record animation invalidation boundaries."""

    settled: list[str] = field(default_factory=list)
    raster_generation_bumps: int = 0

    def settle(self, *, reason: str) -> None:
        """Record one explicit animation settlement."""

        self.settled.append(reason)

    def bump_raster_generation(self) -> None:
        """Record one visual cache generation replacement."""

        self.raster_generation_bumps += 1


@dataclass
class _ClearDouble:
    """Record one cold visual-cache clear."""

    clear_calls: int = 0

    def clear(self) -> None:
        """Record one cache clear."""

        self.clear_calls += 1


@dataclass
class _LiveVisualDouble:
    """Record one live visual invalidation."""

    invalidations: int = 0

    def invalidate(self) -> None:
        """Record invalidation of prepared live visuals."""

        self.invalidations += 1


@dataclass
class _RefreshIdentityDouble:
    """Record visual refresh identity invalidation."""

    invalidations: int = 0

    def invalidate_refresh(self) -> None:
        """Record invalidation of the current refresh identity."""

        self.invalidations += 1


@dataclass
class _RenderDouble:
    """Record render publication commands and style adoption."""

    clear_calls: int = 0
    styles: list[PromptReorderVisualStyle] = field(default_factory=list)
    sync_reasons: list[str] = field(default_factory=list)

    def clear(self) -> None:
        """Record one empty prepared-frame publication."""

        self.clear_calls += 1

    def set_visual_style(self, style: PromptReorderVisualStyle) -> None:
        """Record one replacement immutable visual style."""

        self.styles.append(style)

    def sync(self, *, reason: str) -> None:
        """Record one passive prepared-frame publication."""

        self.sync_reasons.append(reason)


@dataclass
class _PointerRegionsDouble:
    """Record pointer chrome style replacement."""

    styles: list[PromptReorderVisualStyle] = field(default_factory=list)

    def set_visual_style(self, style: PromptReorderVisualStyle) -> None:
        """Record one pointer-region style update."""

        self.styles.append(style)


@dataclass
class _DragProxyDouble:
    """Record drag-proxy lifecycle actions without rendering Qt chrome."""

    font_refreshes: int = 0
    close_calls: int = 0

    def refresh_font(self) -> None:
        """Record one font-derived proxy invalidation."""

        self.font_refreshes += 1

    def ensure_segment_render_state(self, **_kwargs: object) -> bool:
        """Reject unexpected segment rebuilding in the no-document contract."""

        raise AssertionError("theme refresh rebuilt a proxy without document facts")

    def close(self) -> None:
        """Record drag-proxy teardown."""

        self.close_calls += 1


def test_visual_lifecycle_clears_every_visual_cache_once() -> None:
    """One replacement generation clears all visual-only state through its owner."""

    owner, doubles, _geometry_reasons = _owner()

    owner.clear_snapshots(reason="session_reset")

    assert doubles.animation.settled == ["session_reset_snapshot_clear"]
    assert doubles.preview_paints.clear_calls == 1
    assert doubles.preview_visuals.clear_calls == 1
    assert doubles.raster.clear_calls == 1
    assert doubles.live_visuals.invalidations == 1
    assert doubles.refresh_identity.invalidations == 1
    assert doubles.animation.raster_generation_bumps == 1
    assert doubles.render.clear_calls == 1


def test_visual_lifecycle_theme_refresh_stays_on_cold_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A theme refresh replaces visual state without creating drag or geometry work."""

    owner, doubles, geometry_reasons = _owner()
    updated_style = _style(80)
    monkeypatch.setattr(
        PromptReorderVisualStyle,
        "from_current_theme",
        staticmethod(lambda: updated_style),
    )

    owner.refresh_theme(
        PromptReorderThemeRefreshRequest(
            has_document=False,
            dragged_segment=None,
            source_revision=None,
            gesture=cast(PromptReorderGestureStateView, object()),
            gesture_id=None,
            event_id=None,
        )
    )

    assert owner.visual_style is updated_style
    assert doubles.drag_proxy.font_refreshes == 1
    assert doubles.pointer_regions.styles == [updated_style]
    assert doubles.render.styles == [updated_style]
    assert geometry_reasons == []


def test_visual_lifecycle_hides_closes_and_publishes_warm_rasters_only_when_visible() -> (
    None
):
    """Visibility and teardown preserve deterministic visual cleanup ordering."""

    owner, doubles, _geometry_reasons = _owner()

    owner.publish_warmed_rasters(overlay_visible=False)
    owner.publish_warmed_rasters(overlay_visible=True)
    owner.hide()
    owner.close()

    assert doubles.render.sync_reasons == ["raster_warm_batch"]
    assert doubles.animation.settled == [
        "overlay_hide",
        "overlay_hide_snapshot_clear",
        "overlay_close",
        "overlay_close_snapshot_clear",
    ]
    assert doubles.drag_proxy.close_calls == 1


@dataclass
class _LifecycleDoubles:
    """Group the focused visual collaborators for concise owner assertions."""

    animation: _AnimationDouble
    preview_paints: _ClearDouble
    preview_visuals: _ClearDouble
    raster: _ClearDouble
    live_visuals: _LiveVisualDouble
    refresh_identity: _RefreshIdentityDouble
    render: _RenderDouble
    pointer_regions: _PointerRegionsDouble
    drag_proxy: _DragProxyDouble


def _owner() -> tuple[
    PromptReorderOverlayVisualLifecycleOwner,
    _LifecycleDoubles,
    list[str],
]:
    """Build the visual lifecycle owner from only its explicit cold collaborators."""

    doubles = _LifecycleDoubles(
        animation=_AnimationDouble(),
        preview_paints=_ClearDouble(),
        preview_visuals=_ClearDouble(),
        raster=_ClearDouble(),
        live_visuals=_LiveVisualDouble(),
        refresh_identity=_RefreshIdentityDouble(),
        render=_RenderDouble(),
        pointer_regions=_PointerRegionsDouble(),
        drag_proxy=_DragProxyDouble(),
    )
    geometry_reasons: list[str] = []
    owner = PromptReorderOverlayVisualLifecycleOwner(
        visual_style=_style(40),
        animation=cast(PromptReorderAnimationPresentationOwner, doubles.animation),
        preview_paint_snapshots=cast(
            PromptReorderPreviewPaintSnapshotOwner,
            doubles.preview_paints,
        ),
        preview_visuals=cast(PromptReorderPreviewVisualOwner, doubles.preview_visuals),
        raster=cast(PromptReorderRasterPublicationOwner, doubles.raster),
        live_visuals=cast(PromptReorderLiveVisualOwner, doubles.live_visuals),
        refresh_identity=cast(
            PromptReorderRefreshIdentityOwner, doubles.refresh_identity
        ),
        render=cast(PromptReorderRenderPublicationOwner, doubles.render),
        pointer_regions=cast(
            PromptReorderPointerRegionVisualOwner,
            doubles.pointer_regions,
        ),
        drag_proxy=cast(PromptReorderDragProxyVisualOwner, doubles.drag_proxy),
        refresh_geometry=geometry_reasons.append,
    )
    return owner, doubles, geometry_reasons


def _style(alpha: int) -> PromptReorderVisualStyle:
    """Build one deterministic immutable style without reading global Qt theme state."""

    color = QColor(80, 100, 120, alpha)
    return PromptReorderVisualStyle(
        rest_fill=color,
        rest_border=color,
        hover_fill=color,
        hover_border=color,
        active_fill=color,
        active_border=color,
        drag_fill=color,
        drag_border=color,
        marker_color=color,
    )
