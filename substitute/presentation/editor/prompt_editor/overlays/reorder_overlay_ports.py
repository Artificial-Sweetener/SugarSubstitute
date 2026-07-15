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

"""Define typed ports consumed by the reorder overlay shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QScrollBar, QWidget

from substitute.application.prompt_editor import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
)

from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_interaction_geometry import PromptReorderGeometryHost
from ..projection.reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from ..reorder_drag_proxy_state import (
    PromptReorderDragProxyRenderInputs,
    PromptReorderDragProxyRenderStateSync,
)
from .reorder_autoscroll import (
    PromptReorderAutoscrollContext,
    PromptReorderAutoscrollController,
    PromptReorderAutoscrollInvalidation,
)
from .reorder_gesture_controller import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderDragIntent,
)
from .reorder_view import PromptReorderView

if TYPE_CHECKING:
    from .reorder_overlay import _SegmentChip


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayRenderState:
    """Describe prepared reorder chrome state supplied by projection owners."""

    viewport_rect: QRect
    chip_geometry: tuple[object, ...]
    placement_geometry: tuple[object, ...] = ()
    active_segment_index: int | None = None
    preview_payload: object | None = None
    drag_proxy_payload: object | None = None


class PromptReorderOverlay(Protocol):
    """Render prepared reorder chrome and relay drag, commit, and cancel intents."""

    def set_render_state(self, state: PromptReorderOverlayRenderState) -> None:
        """Replace the projection-prepared reorder state rendered by the overlay."""

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the callback used for pointer drag intent."""

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the callback used for commit intent."""

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the callback used for cancel intent."""

    def request_geometry_refresh(self, *, reason: str) -> None:
        """Ask the overlay to refresh its viewport-local geometry."""

    def show_overlay(self) -> None:
        """Show the overlay without taking editor focus."""

    def hide_overlay(self) -> None:
        """Hide the overlay without mutating source text."""


class PromptReorderDragProxyStateFactory(Protocol):
    """Build and cache render state for the floating drag proxy."""

    def reset_counters(self) -> None:
        """Reset deterministic render-state counters for focused tests."""

    def reset_drag_session(self) -> None:
        """Clear any render state tied to a previous drag session."""

    def invalidate(self, *, reason: str) -> None:
        """Invalidate cached drag proxy render state for one explicit reason."""

    def counters(self) -> dict[str, int]:
        """Return deterministic render-state lifecycle counters."""

    def ensure_render_state(
        self,
        inputs: PromptReorderDragProxyRenderInputs,
    ) -> PromptReorderDragProxyRenderStateSync:
        """Return current drag proxy render state for the supplied inputs."""


class PromptReorderViewFactory(Protocol):
    """Create the passive reorder view hosted by the overlay shell."""

    def __call__(self, parent: QWidget) -> PromptReorderView:
        """Return one passive reorder view under the supplied parent."""


class PromptReorderAutoscrollFactory(Protocol):
    """Create the visual autoscroll owner after the overlay QWidget exists."""

    def __call__(
        self,
        overlay: QWidget,
        *,
        step_callback: Callable[[PromptReorderAutoscrollInvalidation], None],
        context_provider: Callable[[], PromptReorderAutoscrollContext],
    ) -> PromptReorderAutoscrollController:
        """Return one autoscroll controller bound to the overlay."""


class PromptReorderEditor(PromptReorderGeometryHost, Protocol):
    """Describe editor APIs consumed by the concrete reorder overlay shell."""

    def document(self) -> QTextDocument:
        """Return the editor document used for text metrics."""

    def viewport(self) -> QWidget:
        """Return the viewport that owns the overlay."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the editor-visible vertical scrollbar."""

    def setFocus(self) -> None:
        """Keep real keyboard focus on the host editor during reorder gestures."""

    def reorder_live_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned live chip geometry for the supplied layout."""

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned preview chip geometry for the supplied layout."""

    def reset_reorder_geometry_cache_counters(self) -> None:
        """Reset deterministic projection geometry counters for focused tests."""

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return deterministic projection geometry counters."""

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible reorder chips."""

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned preview paint snapshots for visible reorder chips."""

    def set_reorder_overlay_suppressed_chip_indices(
        self,
        chip_indices: frozenset[int],
    ) -> None:
        """Suppress live projection painting for chips owned by the overlay."""


class SegmentChipDragController(Protocol):
    """Receive pointer and focus events emitted by concrete segment chip widgets."""

    def set_hovered_segment(self, segment_index: int | None) -> None:
        """Track the segment currently under the pointer."""

    def activate_chip(self, chip: _SegmentChip) -> None:
        """Track the segment that should retain selection on commit."""

    def set_pressed_segment(self, segment_index: int | None) -> None:
        """Track the segment currently held by the pointer."""

    def start_drag(
        self,
        chip: _SegmentChip,
        *,
        global_pos: QPoint,
        press_global_pos: QPoint,
    ) -> None:
        """Begin dragging the supplied chip widget."""

    def drag_move(self, chip: _SegmentChip, global_pos: QPoint) -> None:
        """Update the active drag with one global pointer position."""

    def end_drag(self, chip: _SegmentChip) -> None:
        """Finish the active drag for the supplied chip widget."""

    def retain_editor_focus(self) -> None:
        """Keep real keyboard focus on the host editor during chip interaction."""

    def log_interaction_event(self, event: str, **context: object) -> None:
        """Log prompt-safe chip interaction telemetry without breaking gestures."""


__all__ = [
    "PromptReorderAutoscrollFactory",
    "PromptReorderDragProxyStateFactory",
    "PromptReorderEditor",
    "PromptReorderOverlay",
    "PromptReorderOverlayRenderState",
    "PromptReorderViewFactory",
    "SegmentChipDragController",
]
