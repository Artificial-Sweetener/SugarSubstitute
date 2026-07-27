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

"""Validate and publish transient edit commands before prompt painting."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette, QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from .metrics import PromptProjectionMetrics
from .transient_edit_overlays import (
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)
from .transient_edit_render_state import (
    EMPTY_TRANSIENT_EDIT_RENDER_LAYER,
    PromptTransientDeletionCommand,
    PromptTransientEditLayerKey,
    PromptTransientEditRenderLayer,
    PromptTransientInsertionCommand,
)


class PromptTransientEditRenderLayerOwner:
    """Own validation, preparation, and publication of transient edit commands."""

    def __init__(self) -> None:
        """Create an empty layer with no deferred edit feedback."""

        self._layer = EMPTY_TRANSIENT_EDIT_RENDER_LAYER

    @property
    def layer(self) -> PromptTransientEditRenderLayer:
        """Return the currently published immutable transient layer."""

        return self._layer

    def prepare(
        self,
        *,
        overlays: PromptProjectionTransientEditOverlayController,
        freshness_is_stale_safe: bool,
        source_identity: PromptSourceIdentity,
        metrics: PromptProjectionMetrics,
        viewport_rect: QRectF,
        scroll_offset: float,
        font: QFont,
        palette: QPalette,
    ) -> bool:
        """Publish transient commands only when their complete identity changes."""

        insertion = overlays.valid_insertion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_identity=source_identity,
        )
        deletion = overlays.valid_deletion_overlay(
            freshness_is_stale_safe=freshness_is_stale_safe,
            source_identity=source_identity,
        )
        if insertion is None and deletion is None:
            if self._layer is EMPTY_TRANSIENT_EDIT_RENDER_LAYER:
                return False
            self._layer = EMPTY_TRANSIENT_EDIT_RENDER_LAYER
            return True
        key = PromptTransientEditLayerKey(
            source_identity=source_identity,
            insertion=insertion,
            deletion=deletion,
            metrics_identity=id(metrics),
            viewport=_rect_key(viewport_rect),
            scroll_offset=_coordinate(scroll_offset),
            font_key=font.toString(),
            palette_key=int(palette.cacheKey()),
        )
        if self._layer.key == key:
            return False
        insertion_command = (
            None
            if insertion is None
            else _prepare_insertion(
                insertion,
                overlays=overlays,
                metrics=metrics,
                scroll_offset=scroll_offset,
                font=font,
                palette=palette,
            )
        )
        deletion_command = (
            None
            if deletion is None
            else PromptTransientDeletionCommand(
                rects=tuple(
                    _rect_values(rect)
                    for rect in overlays.deletion_overlay_erase_rects(
                        deletion,
                        scroll_offset=scroll_offset,
                    )
                ),
                background_rgba=int(palette.color(QPalette.ColorRole.Base).rgba()),
            )
        )
        visible_region = overlays.deletion_visible_region(
            deletion,
            viewport_region=QRegion(viewport_rect.toAlignedRect()),
            scroll_offset=scroll_offset,
        )
        self._layer = PromptTransientEditRenderLayer(
            key=key,
            insertion=insertion_command,
            deletion=deletion_command,
            content_visible_region=visible_region,
        )
        return True


def _prepare_insertion(
    overlay: PromptProjectionTransientInsertionOverlay,
    *,
    overlays: PromptProjectionTransientEditOverlayController,
    metrics: PromptProjectionMetrics,
    scroll_offset: float,
    font: QFont,
    palette: QPalette,
) -> PromptTransientInsertionCommand:
    """Prepare one typed-text command from validated transient state."""

    rect = overlays.insertion_overlay_viewport_rect(
        overlay,
        metrics=metrics,
        scroll_offset=scroll_offset,
    )
    return PromptTransientInsertionCommand(
        text=overlay.text,
        rect=_rect_values(rect),
        baseline=metrics.text_baseline_for_row(
            row_top=rect.top(),
            row_height=rect.height(),
        ),
        font=QFont(font),
        text_rgba=int(palette.color(QPalette.ColorRole.Text).rgba()),
        background_rgba=int(palette.color(QPalette.ColorRole.Base).rgba()),
        erase_underlying_content=(
            overlay.committed_source_identity.source_length is None
            or overlay.source_start < overlay.committed_source_identity.source_length
        ),
    )


def _rect_key(rect: QRectF) -> tuple[int, int, int, int]:
    """Quantize one viewport rectangle for exact revision comparison."""

    return (
        _coordinate(rect.x()),
        _coordinate(rect.y()),
        _coordinate(rect.width()),
        _coordinate(rect.height()),
    )


def _rect_values(rect: QRectF) -> tuple[float, float, float, float]:
    """Copy one mutable Qt rectangle into scalar geometry."""

    return rect.x(), rect.y(), rect.width(), rect.height()


def _coordinate(value: float) -> int:
    """Quantize one geometry coordinate without losing subpixel identity."""

    return int(round(value * 100.0))


__all__ = ["PromptTransientEditRenderLayerOwner"]
