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

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)

from ..overlays.reorder_drag_proxy import PromptReorderDragProxyWidget
from ..overlays.reorder_gesture_controller import (
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
)
from ..overlays.reorder_overlay import SegmentReorderOverlay
from ..overlays.reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from ..overlays.reorder_view import PromptReorderView
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..interactions.reorder_overlay_port import PromptReorderOverlayAssembly
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
    PromptReorderLayoutPolicy,
)
from ..projection.reorder_geometry_owner import PromptReorderGeometryOwner
from ..reorder_drag_proxy_state import PromptReorderDragProxyRenderStateBuilder


@dataclass(frozen=True, slots=True)
class PromptSegmentReorderOverlayFactory:
    """Build concrete reorder overlay views for composition wiring."""

    document_service: PromptDocumentService
    syntax_service: PromptSyntaxService
    syntax_profile: PromptSyntaxProfile
    geometry_owner: PromptReorderGeometryOwner
    interaction_metrics: PromptReorderInteractionMetricsOwner

    def create_segment_overlay(
        self,
        editor: QWidget,
        *,
        layout_policy: PromptReorderLayoutPolicy,
    ) -> PromptReorderOverlayAssembly:
        """Return composed reorder authorities for the supplied editor."""

        geometry = PromptReorderInteractionGeometry(
            layout_policy=layout_policy,
            geometry_owner=self.geometry_owner,
        )
        overlay = SegmentReorderOverlay(
            editor,
            geometry=geometry,
            preview_visual_owner=PromptReorderPreviewVisualOwner(
                geometry_state=lambda: geometry.state,
                refresh_preview_geometry=geometry.refresh_preview_geometry,
            ),
            interaction_metrics=self.interaction_metrics,
            view_factory=PromptReorderView,
            gesture_controller=PromptReorderGestureController(),
            drag_proxy_placement=PromptReorderDragProxyPlacementController(),
            drag_proxy=PromptReorderDragProxyWidget(object_name="segmentChipDragProxy"),
            drag_proxy_state_factory=PromptReorderDragProxyRenderStateBuilder(
                document_service=self.document_service,
                syntax_service=self.syntax_service,
                syntax_profile=self.syntax_profile,
            ),
        )
        return PromptReorderOverlayAssembly(
            overlay=overlay,
            preview_build_facts=overlay.preview_build_facts,
            preview_sync_context=overlay.preview_sync_context,
            preview_layout_changed=overlay.previewLayoutChanged,
        )
