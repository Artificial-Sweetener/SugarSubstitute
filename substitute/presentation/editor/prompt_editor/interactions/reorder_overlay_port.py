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

"""Define typed composition ports for one reorder overlay session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptReorderChipView,
)
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewSyncContext,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..overlays.reorder_gesture_controller import PromptReorderDragIntent
from ..projection.reorder_interaction_geometry import PromptReorderLayoutPolicy
from ..projection.reorder_preview_build_facts import PromptReorderPreviewBuildFacts
from .reorder_interaction_metrics import PromptReorderInteractionMetricsOwner


class PromptReorderOverlaySignal(Protocol):
    """Describe the Qt signal seam required from reorder overlays."""

    def connect(self, callback: Callable[[], None]) -> object:
        """Connect one callback to the signal."""


class PromptReorderOverlayPort(Protocol):
    """Expose lifecycle and commands used by interaction orchestration."""

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the callback used for pointer drag intent."""

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the callback used for prepared commit intent."""

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the callback used for cancel intent."""

    def set_chips(
        self,
        document_view: PromptDocumentView,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[PromptReorderChipView, ...],
        active_chip_index: int | None = None,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Populate overlay hotspots from the current reorder-chip snapshot."""

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return prepared reorder state for controller-owned command commit."""

    def set_preview_snapshot(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Apply controller-built preview snapshots."""

    def refresh_geometry(self, *, reason: str = "unspecified") -> None:
        """Refresh overlay geometry."""

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Apply pending autoscroll geometry invalidation if one exists."""

    def needs_position_refresh(self, *, reason: str = "unspecified") -> bool:
        """Return whether viewport positioning inputs changed."""

    def move_active_chip(self, intent: PromptReorderKeyboardMoveIntent) -> bool:
        """Apply one typed keyboard move when possible."""

    def cancel_drag(self) -> None:
        """Clear drag visuals without mutating source."""

    def show(self) -> None:
        """Show the overlay."""

    def close(self) -> bool:
        """Close the overlay."""

    def deleteLater(self) -> None:  # noqa: N802
        """Schedule overlay deletion."""


class PromptReorderPreviewBuildFactsPort(Protocol):
    """Publish one immutable preview-build generation."""

    def snapshot(self) -> PromptReorderPreviewBuildFacts:
        """Return coherent facts for one projection build."""


class PromptReorderPreviewSyncContextPort(Protocol):
    """Publish one immutable preview-scheduling context."""

    def snapshot(self) -> PromptReorderPreviewSyncContext:
        """Return coherent facts for one scheduling decision."""


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayAssembly:
    """Carry separately typed overlay and preview-fact authorities."""

    overlay: PromptReorderOverlayPort
    preview_build_facts: PromptReorderPreviewBuildFactsPort
    preview_sync_context: PromptReorderPreviewSyncContextPort
    preview_layout_changed: PromptReorderOverlaySignal


class PromptReorderOverlayFactory(Protocol):
    """Create typed reorder overlay authorities for interaction orchestration."""

    @property
    def interaction_metrics(self) -> PromptReorderInteractionMetricsOwner:
        """Return the metrics owner shared with every created overlay."""

    def create_segment_overlay(
        self,
        editor: QWidget,
        *,
        layout_policy: PromptReorderLayoutPolicy,
    ) -> PromptReorderOverlayAssembly:
        """Return one composed reorder overlay session."""


__all__ = [
    "PromptReorderDragIntent",
    "PromptReorderOverlayAssembly",
    "PromptReorderOverlayFactory",
    "PromptReorderOverlayPort",
    "PromptReorderPreviewBuildFactsPort",
    "PromptReorderPreviewSyncContextPort",
]
