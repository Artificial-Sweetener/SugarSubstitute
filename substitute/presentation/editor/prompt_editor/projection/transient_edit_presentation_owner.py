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

"""Own transient edit overlay geometry and viewport repaint publication."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from .metrics import PromptProjectionMetrics
from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)


class PromptTransientEditPresentation(Protocol):
    """Publish changed transient edit feedback to its mounted viewport."""

    def update_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Publish and repaint changed insertion feedback."""

    def update_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Publish and repaint changed deletion feedback."""


class PromptTransientEditPresentationOwner:
    """Resolve overlay paint geometry and invalidate its exact viewport area."""

    def __init__(
        self,
        *,
        overlays: PromptProjectionTransientEditOverlayController,
        metrics: Callable[[], PromptProjectionMetrics],
        scroll_offset: Callable[[], float],
        viewport: QWidget,
        publish_render_frame: Callable[[], None],
    ) -> None:
        """Bind overlay state to the live geometry and mounted paint target."""

        self._overlays = overlays
        self._metrics = metrics
        self._scroll_offset = scroll_offset
        self._viewport = viewport
        self._publish_render_frame = publish_render_frame

    def insertion_overlay_viewport_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the viewport-local paint rect for one insertion overlay."""

        return self._overlays.insertion_overlay_viewport_rect(
            overlay,
            metrics=self._metrics(),
            scroll_offset=self._scroll_offset(),
        )

    def insertion_overlay_document_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the document-local paint rect for one insertion overlay."""

        return self._overlays.insertion_overlay_document_rect(
            overlay,
            metrics=self._metrics(),
        )

    def deletion_overlay_viewport_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
    ) -> tuple[QRectF, ...]:
        """Return viewport-local erase rects for one deletion overlay."""

        return self._overlays.deletion_overlay_viewport_rects(
            overlay,
            scroll_offset=self._scroll_offset(),
        )

    def deletion_overlay_erase_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
    ) -> tuple[QRectF, ...]:
        """Return expanded deletion erase bands grouped by visual row."""

        return self._overlays.deletion_overlay_erase_rects(
            overlay,
            scroll_offset=self._scroll_offset(),
        )

    def update_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Publish and repaint transient typed text after its state changes."""

        repaint_rect = self._overlays.insertion_overlay_repaint_rect(
            previous_overlay=previous_overlay,
            next_overlay=next_overlay,
            metrics=self._metrics(),
            scroll_offset=self._scroll_offset(),
        )
        self._publish_render_frame()
        if repaint_rect is not None:
            self._viewport.update(repaint_rect.toAlignedRect())

    def update_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Publish and repaint transient erased text after its state changes."""

        repaint_rect = self._overlays.deletion_overlay_repaint_rect(
            previous_overlay=previous_overlay,
            next_overlay=next_overlay,
            scroll_offset=self._scroll_offset(),
        )
        self._publish_render_frame()
        if repaint_rect is not None:
            self._viewport.update(repaint_rect.toAlignedRect())


__all__ = [
    "PromptTransientEditPresentation",
    "PromptTransientEditPresentationOwner",
]
