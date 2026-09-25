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

"""Render the Output CuteCanvas workspace and application navigation chrome."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from cutecanvas import CanvasPresentation, ExecutionRuntime, OutboundMimeProvider

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.output_canvas_route_scope import (
    build_output_route_scope,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_compare_resolution import (
    reconcile_output_compare_state,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_results import (
    OutputPreviewAcceptance,
)
from substitute.presentation.canvas.output.output_canvas_chrome import (
    install_output_navigation_chrome_theme_refresh,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_document import (
    OutputCanvasDocument,
)
from substitute.presentation.canvas.output.output_document_navigation import (
    OutputDocumentNavigation,
)
from substitute.presentation.canvas.output.output_document_preview_presenter import (
    OutputDocumentPreviewPresenter,
)
from substitute.presentation.canvas.output.output_canvas_localization import (
    retranslate_output_canvas,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_navigation_layout_adapter import (
    OutputNavigationLayoutAdapter,
)
from substitute.presentation.canvas.output.output_document_route_projector import (
    OutputDocumentRouteProjector,
)
from substitute.presentation.canvas.output.output_projection_content_synchronizer import (
    OutputProjectionContentSynchronizer,
)
from substitute.presentation.canvas.output.output_preview_navigation_presenter import (
    OutputPreviewNavigationPresenter,
)
from substitute.presentation.canvas.output.output_projection_presenter import (
    OutputProjectionPresenter,
)
from substitute.presentation.canvas.output.output_canvas_zoom_indicators import (
    OutputCanvasZoomIndicators,
)
from substitute.application.ports.video import VideoPlaybackEvent, VideoPlayerPort
from substitute.domain.generation import VideoPlaybackSettings
from substitute.presentation.canvas.output.output_video_presentation_coordinator import (
    OutputVideoPresentationCoordinator,
)
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapCoordinator,
)
from substitute.presentation.canvas.output.output_navigation_widgets import (
    create_output_navigation_widgets,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta

_SCENE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MIN_WIDTH = 58


class OutputCanvas(QWidget):
    """Host one read-only CuteCanvas Output document and its navigation chrome."""

    tabbar_container: QWidget

    activeOutputChanged = Signal(str)
    activeOutputGridChanged = Signal(str)
    activeOutputSceneChanged = Signal(object)
    activeOutputCompareChanged = Signal(object)
    dockActionRequested = Signal()

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
        video_player_factory: Callable[
            [Callable[[VideoPlaybackEvent], None]], VideoPlayerPort
        ]
        | None = None,
        video_settings_provider: Callable[[], VideoPlaybackSettings] | None = None,
    ) -> None:
        """Create the one Output document workspace and host-owned chrome."""

        super().__init__(parent)
        if route_session_boundary is None:
            raise ValueError("Output canvas requires the shared route session boundary")
        self._unscoped_preview_image_id = uuid4()
        self.setStyleSheet("border: none; background-color: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._open_single_external_editor = open_single_external_editor
        self._open_all_external_editor = open_all_external_editor
        self._reveal_output_asset = reveal_output_asset
        self._asset_lookup = OutputCanvasAssetLookup(
            payload_lookup=final_output_payload_lookup,
            metadata_lookup=final_output_metadata_lookup,
        )
        self._preview_registry = preview_registry
        self._canvas_detached = False
        self._output_session: OutputCanvasSession | None = None
        self._output_projection: OutputCanvasProjection | None = None
        self._visible_compare_state = OutputCompareState()
        self.active_source_key: str | None = None
        self.active_scene_key: str | None = None
        self.active_scene_overview = False
        self.scene_count = 0
        self.active_set_index = 1
        self.last_real_set_index = 1
        self.set_count = 0
        self._suppress_tab_change = False
        self._source_tabs_collapsed = False
        self._source_tabbar_preferred_width = 0
        self._source_tab_cache_signature: tuple[tuple[str, str], ...] | None = None
        self._source_tab_tooltip_filters: dict[str, object] = {}

        self.document = OutputCanvasDocument(
            execution_runtime=execution_runtime,
        )
        output_document = self.document
        self.destroyed.connect(
            lambda _object=None, document=output_document: document.close()
        )
        self.workspace = self.document.workspace
        self._route_projector = OutputDocumentRouteProjector(
            self.document,
            session_boundary=route_session_boundary,
        )
        self.workspace.targetActivated.connect(self._activate_workspace_target)
        self.workspace.presentationChanged.connect(
            self._handle_workspace_presentation_change
        )
        self._transfer_context_handler: Callable[[object, object], None] | None = None

        workspace_layout = QVBoxLayout(self)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.video_presentation = OutputVideoPresentationCoordinator(
            parent=self,
            workspace=self.workspace,
            document=self.document,
            metadata_for=self._asset_lookup.final_output_metadata,
            player_factory=video_player_factory,
            video_settings_provider=video_settings_provider,
        )
        workspace_layout.addWidget(self.video_presentation.widget)
        self._compare_material_gap = OutputCompareMaterialGapCoordinator(self.workspace)
        self._zoom_indicators = OutputCanvasZoomIndicators(self.workspace)

        navigation_widgets = create_output_navigation_widgets(
            self,
            scene_selector_min_width=_SCENE_SELECTOR_MIN_WIDTH,
            source_selector_min_width=_SOURCE_SELECTOR_MIN_WIDTH,
        )
        self.tabbar_container = navigation_widgets.tabbar_container
        self.tabbar_bg = navigation_widgets.tabbar_bg
        self.scene_selector_button = navigation_widgets.scene_selector_button
        self.set_selector_button = navigation_widgets.set_selector_button
        self.source_selector_button = navigation_widgets.source_selector_button
        self.tabbar = navigation_widgets.tabbar
        self._set_picker = navigation_widgets.set_picker
        self._scene_picker = navigation_widgets.scene_picker
        self._source_picker = navigation_widgets.source_picker
        self.comparison_nav_container = navigation_widgets.comparison_nav_container
        self.comparison_nav_bg = navigation_widgets.comparison_nav_bg
        self.comparison_scene_selector_button = (
            navigation_widgets.comparison_scene_selector_button
        )
        self.comparison_set_selector_button = (
            navigation_widgets.comparison_set_selector_button
        )
        self.comparison_source_selector_button = (
            navigation_widgets.comparison_source_selector_button
        )
        self._navigation_controller = OutputNavigationLayoutAdapter(
            canvas_width=self.width,
            tabbar=lambda: self.tabbar,
            cached_source_tabbar_width=lambda: self._source_tabbar_preferred_width,
            set_cached_source_tabbar_width=lambda width: setattr(
                self,
                "_source_tabbar_preferred_width",
                width,
            ),
        )
        self._document_navigation = OutputDocumentNavigation(self)
        self._preview_navigation = OutputPreviewNavigationPresenter(self)
        self._projection_presenter = OutputProjectionPresenter(
            document=self.document,
            document_navigation=self._document_navigation,
            preview_navigation=self._preview_navigation,
            route_projector=self._route_projector,
        )
        self._preview_presenter = OutputDocumentPreviewPresenter(
            preview_registry=lambda: self._preview_registry,
            document=self.document,
            output_session=lambda: self._output_session,
            refresh_preview_scope=self._bind_preview_scope,
            present_source_preview=self._preview_navigation.present_source_preview,
            present_scene_previews=self._preview_navigation.present_scene_previews,
        )
        install_output_navigation_chrome_theme_refresh(
            host=self,
            base_background=self.tabbar_bg,
            comparison_background=self.comparison_nav_bg,
        )
        update_output_tabbar_container(self)

    @property
    def route_projector(self) -> OutputDocumentRouteProjector:
        """Return the guarded document route projector for this Output surface."""

        return self._route_projector

    @property
    def visible_compare_state(self) -> OutputCompareState:
        """Return the compare state currently rendered by the Output workspace."""

        return self._visible_compare_state

    @property
    def canvas_detached(self) -> bool:
        """Return whether the manager has detached this canvas from its dock."""

        return self._canvas_detached

    def set_compare_mode_enabled(self, enabled: bool) -> None:
        """Request the Output navigation owner update visible compare mode."""

        self._document_navigation.set_compare_mode_enabled(enabled)

    def final_output_metadata(self, image_id: UUID) -> OutputImageMeta | None:
        """Resolve one final Output image's metadata for a host action."""

        return self._asset_lookup.final_output_metadata(image_id)

    @property
    def single_external_editor(
        self,
    ) -> Callable[[object, OutputImageMeta], bool] | None:
        """Return the optional host integration for opening one Output image."""

        return self._open_single_external_editor

    @property
    def all_external_editor(
        self,
    ) -> Callable[[list[tuple[object, OutputImageMeta]]], bool] | None:
        """Return the optional host integration for opening Output collections."""

        return self._open_all_external_editor

    @property
    def output_asset_revealer(self) -> Callable[[OutputImageMeta], bool] | None:
        """Return the optional host integration for revealing one Output asset."""

        return self._reveal_output_asset

    def set_final_output_lookup(
        self,
        *,
        payload_lookup: Callable[[UUID], object | None],
        metadata_lookup: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Store application-owned final asset lookup callbacks for later actions."""

        self._asset_lookup.set_final_output_lookup(
            payload_lookup=payload_lookup,
            metadata_lookup=metadata_lookup,
        )
        self.video_presentation.refresh_badges()

    def install_transfer_drag_provider(self, provider: OutboundMimeProvider) -> None:
        """Install one composed outbound MIME provider on every workspace target."""

        if not callable(getattr(provider, "materialize", None)):
            raise TypeError(
                "Output transfer provider must implement OutboundMimeProvider"
            )
        self.workspace.setOutboundMimeProvider(provider)

    def install_transfer_context_handler(
        self,
        handler: Callable[[object, object], None],
    ) -> None:
        """Forward public CuteCanvas content-context requests to one UI presenter."""

        if self._transfer_context_handler is not None:
            self.workspace.contentContextRequested.disconnect(
                self._transfer_context_handler
            )
        self.workspace.contentContextRequested.connect(handler)
        self._transfer_context_handler = handler

    def create_projection_content_synchronizer(
        self,
        image_registry: object,
    ) -> OutputProjectionContentSynchronizer:
        """Create the presentation adapter that admits registry payloads to this document."""

        from substitute.application.workflows.canvas_image_registry import (
            CanvasImageRegistry,
        )

        if not isinstance(image_registry, CanvasImageRegistry):
            raise TypeError(
                "Output content synchronization requires CanvasImageRegistry"
            )
        return OutputProjectionContentSynchronizer(
            image_registry=image_registry,
            output_document=self.document,
        )

    def set_preview_registry(self, registry: OutputPreviewRegistry) -> None:
        """Replace the application-owned transient preview registry."""

        self._preview_registry = registry

    def apply_preview_acceptance(
        self,
        acceptance: OutputPreviewAcceptance,
    ) -> None:
        """Apply a session-authorized preview through the document presenter."""

        self._preview_presenter.apply_preview_acceptance(acceptance)

    def close_final_output_preview_lane(
        self,
        identity: OutputPreviewCloseIdentity,
    ) -> None:
        """Retire preview compositions replaced by one final Output image."""

        if identity.batch_index in {None, 0}:
            self._preview_navigation.release_automatic_follow()
        close_result = self._preview_registry.close_final_output_lane(identity)
        self._preview_presenter.close_final_output_preview_lane(
            close_result.closed_preview_ids
        )

    def release_automatic_preview_follow(self) -> None:
        """Let the newest final output replace transient Automatic preview focus."""

        self._preview_navigation.release_automatic_follow()

    def clear_previews(self, source_key: str | None = None) -> None:
        """Retire transient preview compositions without affecting final content."""

        self._preview_presenter.clear_previews(source_key=source_key)

    def set_canvas_detached(self, detached: bool) -> None:
        """Store manager-owned attachment state for future context-menu rendering."""

        self._canvas_detached = detached

    def prepare_for_window_transition(self) -> None:
        """Release native video rendering before this canvas changes windows."""

        self.video_presentation.prepare_for_window_transition()

    def complete_window_transition(self) -> None:
        """Resume native video rendering in this canvas's settled window."""

        self.video_presentation.complete_window_transition()
        update_output_tabbar_container(self)

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Apply one authorized projection through the Output document workspace."""

        self.document.validate_detail_inspection_groups(
            workflow_id=session.workflow_id.value,
            groups=session.detail_inspection_groups,
        )
        previous_source_key = self.active_source_key
        previous_set_index = self.active_set_index
        previous_scene_key = self.active_scene_key
        previous_scene_overview = self.active_scene_overview
        retired_preview_ids = self._preview_registry.rebind_workflow_session(session)
        self._preview_presenter.close_final_output_preview_lane(retired_preview_ids)
        self._output_session = session
        projection = session.projection
        self._output_projection = projection
        self.scene_count = projection.scene_count
        self.active_scene_key = projection.active_scene_key
        self.active_scene_overview = projection.active_scene_overview
        self.active_source_key = projection.active_source_key
        self.active_set_index = projection.active_set_index
        self._preview_navigation.restore_selection(
            previous_scene_key,
            previous_scene_overview,
            previous_source_key,
            previous_set_index,
        )
        if self.active_set_index > 0:
            self.last_real_set_index = self.active_set_index
        self.set_count = projection.set_count
        self._route_projector.bind(
            build_output_route_scope(
                session=session,
                preview_lanes=self._preview_registry.lanes_for_session(session),
                active_scene_overview=self.active_scene_overview,
                active_scene_key=self.active_scene_key,
            )
        )
        self.document.set_detail_inspection_groups(
            workflow_id=session.workflow_id.value,
            groups=session.detail_inspection_groups,
        )
        compare_state = reconcile_output_compare_state(
            projection,
            projection.compare_state,
        )
        self._visible_compare_state = compare_state
        self._document_navigation.synchronize_projection()
        self._projection_presenter.present(
            projection,
            compare_state=compare_state,
            active_scene_overview=self.active_scene_overview,
            active_source_key=self.active_source_key,
            active_set_index=self.active_set_index,
        )

    def discard_workflow_detail_groups(self, workflow_id: str) -> None:
        """Release retained Output inspection state for a closed workflow."""

        self.document.discard_workflow_detail_groups(workflow_id)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update host-owned navigation overlay geometry after a workspace resize."""

        update_output_tabbar_container(self)
        super().resizeEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh localized Output chrome without changing document content."""

        if event.type() == QEvent.Type.LanguageChange:
            retranslate_output_canvas(self)
        super().changeEvent(event)

    def _bind_preview_scope(self) -> None:
        """Refresh authorized document members after preview registry mutation."""

        if self._output_session is None:
            return
        self._document_navigation.synchronize_projection()
        session = self._output_session
        if session is None:
            return
        self._route_projector.bind(
            build_output_route_scope(
                session=session,
                preview_lanes=self._preview_registry.lanes_for_session(session),
                active_scene_overview=self.active_scene_overview,
                active_scene_key=self.active_scene_key,
            )
        )

    def present_preview_selection(self, preview_id: UUID) -> None:
        """Present one user-selected placeholder and preserve it across final refreshes."""

        self._preview_navigation.present_selection(preview_id)

    def present_preview_grid(self, image_ids: tuple[UUID, ...]) -> None:
        """Present one user-selected grid containing a transient placeholder."""

        self._preview_navigation.present_grid(image_ids)

    def release_preview_navigation(self) -> None:
        """Release transient focus before normal final-output navigation."""

        self._preview_navigation.release()

    def _activate_workspace_target(self, composition_id: UUID) -> None:
        """Forward one document-grid activation to existing Output navigation signals."""

        image_id = self.document.image_id_for_composition(composition_id)
        if image_id is None:
            return
        self._document_navigation.activate_grid_target(image_id)

    def _handle_workspace_presentation_change(self, presentation: object) -> None:
        """Forward public CuteCanvas divider changes to persisted compare state."""

        if isinstance(presentation, CanvasPresentation):
            self._document_navigation.handle_workspace_presentation(presentation)
            self.video_presentation.synchronize(presentation)
            update_output_tabbar_container(self)


__all__ = ["OutputCanvas"]
