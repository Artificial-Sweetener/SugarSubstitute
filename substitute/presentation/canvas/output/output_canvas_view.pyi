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

"""Typing surface for the public CuteCanvas Output workspace widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from cutecanvas import ExecutionRuntime, OutboundMimeProvider

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_results import (
    OutputPreviewAcceptance,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_document_route_projector import (
    OutputDocumentRouteProjector,
)
from substitute.presentation.canvas.output.output_projection_content_synchronizer import (
    OutputProjectionContentSynchronizer,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta

class OutputCanvas(QWidget):
    """Expose the document-backed Output workspace and projection binding API."""

    activeOutputChanged: Signal
    activeOutputGridChanged: Signal
    activeOutputSceneChanged: Signal
    activeOutputCompareChanged: Signal
    dockActionRequested: Signal
    document: OutputCanvasDocument
    workspace: Any
    tabbar: Any
    scene_selector_button: Any
    set_selector_button: Any
    source_selector_button: Any
    comparison_scene_selector_button: Any
    comparison_set_selector_button: Any
    comparison_source_selector_button: Any
    active_scene_overview: bool
    active_scene_key: str | None
    active_source_key: str | None
    active_set_index: int
    scene_count: int
    set_count: int
    _output_projection: OutputCanvasProjection | None
    _output_session: OutputCanvasSession | None
    _preview_registry: OutputPreviewRegistry
    _preview_navigation: Any
    _document_navigation: Any
    _set_picker: Any
    _scene_picker: Any
    _source_picker: Any
    _zoom_indicators: Any

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        execution_runtime: ExecutionRuntime | None = None,
        preview_registry: OutputPreviewRegistry,
        open_single_external_editor: (
            Callable[[object, OutputImageMeta], bool] | None
        ) = None,
        open_all_external_editor: (
            Callable[[list[tuple[object, OutputImageMeta]]], bool] | None
        ) = None,
        reveal_output_asset: Callable[[OutputImageMeta], bool] | None = None,
        final_output_payload_lookup: Callable[[UUID], object | None] | None = None,
        final_output_metadata_lookup: (
            Callable[[UUID], OutputImageMeta | None] | None
        ) = None,
        route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
    ) -> None: ...
    @property
    def route_projector(self) -> OutputDocumentRouteProjector:
        """Return the authorized document route projector for this widget."""
        ...
    @property
    def visible_compare_state(self) -> OutputCompareState:
        """Return the compare state currently rendered by the Output workspace."""
        ...
    @property
    def canvas_detached(self) -> bool:
        """Return whether the Output canvas is currently detached from its dock."""
        ...
    def set_compare_mode_enabled(self, enabled: bool) -> None:
        """Request the Output navigation owner update visible compare mode."""
        ...
    def final_output_metadata(self, image_id: UUID) -> OutputImageMeta | None:
        """Resolve one final Output image's metadata for a host action."""
        ...
    @property
    def single_external_editor(
        self,
    ) -> Callable[[object, OutputImageMeta], bool] | None:
        """Return the optional host integration for opening one Output image."""
        ...
    @property
    def all_external_editor(
        self,
    ) -> Callable[[list[tuple[object, OutputImageMeta]]], bool] | None:
        """Return the optional host integration for opening Output collections."""
        ...
    @property
    def output_asset_revealer(self) -> Callable[[OutputImageMeta], bool] | None:
        """Return the optional host integration for revealing one Output asset."""
        ...
    def create_projection_content_synchronizer(
        self,
        image_registry: CanvasImageRegistry,
    ) -> OutputProjectionContentSynchronizer:
        """Create the document admission adapter for authoritative payloads."""
        ...
    def set_final_output_lookup(
        self,
        *,
        payload_lookup: Callable[[UUID], object | None],
        metadata_lookup: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Accept application-owned final lookup callbacks for later actions."""
        ...
    def set_preview_registry(self, registry: OutputPreviewRegistry) -> None:
        """Bind the transient preview registry for the active projection surface."""
        ...
    def install_transfer_drag_provider(self, provider: OutboundMimeProvider) -> None:
        """Install one composed outbound MIME provider on every workspace target."""
        ...
    def install_transfer_context_handler(
        self, handler: Callable[[object, object], None]
    ) -> None:
        """Forward workspace content-context requests to one UI presenter."""
        ...

    def _activate_workspace_target(self, composition_id: UUID) -> None:
        """Translate one workspace activation into Output navigation intent."""
        ...
    def apply_preview_acceptance(self, acceptance: OutputPreviewAcceptance) -> None:
        """Admit and display one accepted preview payload."""
        ...
    def close_final_output_preview_lane(
        self, identity: OutputPreviewCloseIdentity
    ) -> None:
        """Retire previews superseded by one final Output image."""
        ...
    def clear_previews(self, source_key: str | None = None) -> None:
        """Retire transient previews for one source or all sources."""
        ...
    def present_preview_selection(self, preview_id: UUID) -> None:
        """Present one user-selected transient placeholder."""
        ...
    def present_preview_grid(self, image_ids: tuple[UUID, ...]) -> None:
        """Present one user-selected grid containing a transient placeholder."""
        ...
    def release_preview_navigation(self) -> None:
        """Return navigation ownership to durable final outputs."""
        ...
    def set_canvas_detached(self, detached: bool) -> None:
        """Set manager-owned canvas attachment state."""
        ...
    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Bind the active Output projection session into the workspace."""
        ...
