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

"""Create concrete reorder overlays for composition-owned wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtWidgets import QScrollBar, QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)

from ..overlays.reorder_drag_proxy import PromptReorderDragProxyWidget
from ..overlays.reorder_autoscroll import (
    PromptReorderAutoscrollContext,
    PromptReorderAutoscrollController,
    PromptReorderAutoscrollInvalidation,
)
from ..overlays.reorder_gesture_controller import (
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
)
from ..overlays.reorder_overlay import SegmentReorderOverlay
from ..overlays.reorder_view import PromptReorderView
from ..projection.reorder_interaction_geometry import (
    PromptReorderGeometryHost,
    PromptReorderInteractionGeometry,
    PromptReorderLayoutPolicy,
)
from ..reorder_drag_proxy_state import PromptReorderDragProxyRenderStateBuilder


class _PromptSegmentReorderEditor(PromptReorderGeometryHost, Protocol):
    """Describe editor APIs composition needs for reorder overlay wiring."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the editor-visible scrollbar used by autoscroll."""


@dataclass(frozen=True, slots=True)
class _PromptReorderAutoscrollFactory:
    """Create autoscroll controllers after the overlay QWidget exists."""

    editor: _PromptSegmentReorderEditor

    def __call__(
        self,
        overlay: QWidget,
        *,
        step_callback: Callable[[PromptReorderAutoscrollInvalidation], None],
        context_provider: Callable[[], PromptReorderAutoscrollContext],
    ) -> PromptReorderAutoscrollController:
        """Return an autoscroll controller bound to the overlay and editor."""

        return PromptReorderAutoscrollController(
            parent=overlay,
            scrollbar_provider=self.editor.verticalScrollBar,
            overlay_height_provider=overlay.height,
            map_global_to_overlay=overlay.mapFromGlobal,
            step_callback=step_callback,
            context_provider=context_provider,
        )


@dataclass(frozen=True, slots=True)
class PromptSegmentReorderOverlayFactory:
    """Build concrete reorder overlay views for composition wiring."""

    document_service: PromptDocumentService
    syntax_service: PromptSyntaxService
    syntax_profile: PromptSyntaxProfile

    def create_segment_overlay(
        self,
        editor: QWidget,
        *,
        layout_policy: PromptReorderLayoutPolicy,
    ) -> SegmentReorderOverlay:
        """Return one concrete segment reorder overlay for the supplied editor."""

        geometry = PromptReorderInteractionGeometry(
            layout_policy=layout_policy,
            geometry_host=cast_reorder_geometry_host(editor),
        )
        return SegmentReorderOverlay(
            editor,
            geometry=geometry,
            view_factory=PromptReorderView,
            gesture_controller=PromptReorderGestureController(),
            drag_proxy_placement=PromptReorderDragProxyPlacementController(),
            autoscroll_factory=_PromptReorderAutoscrollFactory(
                cast_segment_reorder_editor(editor)
            ),
            drag_proxy=PromptReorderDragProxyWidget(object_name="segmentChipDragProxy"),
            drag_proxy_state_factory=PromptReorderDragProxyRenderStateBuilder(
                document_service=self.document_service,
                syntax_service=self.syntax_service,
                syntax_profile=self.syntax_profile,
            ),
        )


def cast_reorder_geometry_host(editor: QWidget) -> PromptReorderGeometryHost:
    """Return the editor through the reorder geometry host protocol."""

    return cast(PromptReorderGeometryHost, editor)


def cast_segment_reorder_editor(editor: QWidget) -> _PromptSegmentReorderEditor:
    """Return the editor through the full reorder composition protocol."""

    return cast(_PromptSegmentReorderEditor, editor)
