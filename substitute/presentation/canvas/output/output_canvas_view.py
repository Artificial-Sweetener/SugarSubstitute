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

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from cutecanvas import ExecutionRuntime, OutboundMimeProvider

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    CanvasRouteSessionBoundaryPort,
    OutputRouteScope,
)
from substitute.application.workflows.output_canvas_route_scope import (
    output_route_scope_members,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    output_route_identity_for_projection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_compare_resolution import (
    reconcile_output_compare_state,
    resolve_output_compare_selection,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewLane,
    OutputPreviewRegistry,
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
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_document_route_projector import (
    OutputDocumentRouteProjector,
)
from substitute.presentation.canvas.output.output_projection_content_synchronizer import (
    OutputProjectionContentSynchronizer,
)
from substitute.presentation.canvas.output.output_canvas_zoom_indicators import (
    OutputCanvasZoomIndicators,
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
        workspace_layout.addWidget(self.workspace)
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
        self._navigation_controller = OutputCanvasNavigationController(
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
        self._preview_presenter = OutputDocumentPreviewPresenter(
            preview_registry=lambda: self._preview_registry,
            document=self.document,
            output_session=lambda: self._output_session,
            refresh_preview_scope=self._bind_preview_scope,
            present_source_preview=self._present_source_preview,
            present_scene_previews=self._present_scene_previews,
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

        close_result = self._preview_registry.close_final_output_lane(identity)
        self._preview_presenter.close_final_output_preview_lane(
            close_result.closed_preview_ids
        )

    def clear_previews(self, source_key: str | None = None) -> None:
        """Retire transient preview compositions without affecting final content."""

        self._preview_presenter.clear_previews(source_key=source_key)

    def set_canvas_detached(self, detached: bool) -> None:
        """Store manager-owned attachment state for future context-menu rendering."""

        self._canvas_detached = detached

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Apply one authorized projection through the Output document workspace."""

        self._output_session = session
        projection = session.projection
        self._output_projection = projection
        self.scene_count = projection.scene_count
        self.active_scene_key = projection.active_scene_key
        self.active_scene_overview = projection.active_scene_overview
        self.active_source_key = projection.active_source_key
        self.active_set_index = projection.active_set_index
        if self.active_set_index > 0:
            self.last_real_set_index = self.active_set_index
        self.set_count = projection.set_count
        self._route_projector.bind(
            OutputRouteScope(
                session=session,
                allowed_image_ids=session.allowed_image_ids,
                allowed_source_keys=session.allowed_source_keys,
                allowed_scene_keys=session.allowed_scene_keys,
                allowed_composition_ids=session.allowed_composition_ids,
            )
        )
        self.document.set_detail_inspection_groups(
            workflow_id=session.workflow_id.value,
            groups=session.detail_inspection_groups,
        )
        self._present_projection(projection)
        self._document_navigation.synchronize_projection()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update host-owned navigation overlay geometry after a workspace resize."""

        update_output_tabbar_container(self)
        super().resizeEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Refresh localized Output chrome without changing document content."""

        if event.type() == QEvent.Type.LanguageChange:
            retranslate_output_canvas(self)
        super().changeEvent(event)

    def _present_projection(self, projection: OutputCanvasProjection) -> None:
        """Choose exactly one document presentation for the current projection."""

        compare_state = reconcile_output_compare_state(
            projection,
            projection.compare_state,
        )
        self._visible_compare_state = compare_state
        if compare_state.enabled and compare_state.base and compare_state.comparison:
            base = resolve_output_compare_selection(projection, compare_state.base)
            comparison = resolve_output_compare_selection(
                projection,
                compare_state.comparison,
            )
            if base is not None and comparison is not None:
                if self.document.present_comparison(
                    base.image_id,
                    comparison.image_id,
                    split_position=compare_state.split_position,
                    orientation=compare_state.orientation,
                ):
                    return
        if projection.active_scene_overview:
            session = self._output_session
            preview_scenes = (
                self._preview_registry.preview_scene_groups(session)
                if session is not None
                else {}
            )
            self.document.present_grid(
                _scene_overview_image_ids(
                    projection,
                    preview_scenes=preview_scenes,
                )
            )
            return
        sources = _visible_sources(projection)
        if projection.active_set_index == 0:
            source = next(
                (
                    source
                    for source in sources
                    if source.source_key == projection.active_source_key
                ),
                None,
            )
            if source is not None:
                self.document.present_grid(_source_image_ids(source))
                return
        if projection.active_uuid is not None:
            self._route_projector.apply_final_image_route(
                output_route_identity_for_projection(projection),
                projection.active_uuid,
            )
            return
        self.document.clear_presentation()

    def _bind_preview_scope(self) -> None:
        """Refresh authorized document members after preview registry mutation."""

        session = self._output_session
        if session is None:
            return
        members = output_route_scope_members(
            session=session,
            route=session.active_route,
            preview_lanes=self._preview_registry.lanes_for_session(session),
            active_scene_overview=self.active_scene_overview,
            active_scene_key=self.active_scene_key,
        )
        self._route_projector.bind(
            OutputRouteScope(
                session=session,
                allowed_image_ids=members.image_ids,
                allowed_source_keys=members.source_keys,
                allowed_scene_keys=members.scene_keys,
                allowed_composition_ids=members.composition_ids,
            )
        )

    def _present_source_preview(self, preview_id: UUID) -> None:
        """Present one authorized source preview through the document route boundary."""

        self._route_projector.apply_final_image_route(
            CanvasRouteIdentity(
                route_kind="output_image",
                route_key=f"image:{preview_id}",
                primary_image_id=preview_id,
            ),
            preview_id,
        )

    def _present_scene_previews(
        self,
        lanes: tuple[OutputPreviewLane, ...],
    ) -> None:
        """Present accepted scene-preview representatives when overview is active."""

        session = self._output_session
        if session is None:
            return
        preview_scenes = self._preview_registry.preview_scene_groups(session)
        if not preview_scenes:
            return
        reported_scene_count = max(
            (lane.scene_count or 0 for lane in lanes),
            default=0,
        )
        self.scene_count = max(
            self.scene_count,
            reported_scene_count,
            len(preview_scenes),
        )
        if self.scene_count > 1 and self.active_scene_key is None:
            self.active_scene_key = next(iter(preview_scenes), None)
            self.active_scene_overview = True
        if not self.active_scene_overview:
            return
        image_ids = _scene_overview_image_ids(
            self._output_projection,
            preview_scenes=preview_scenes,
        )
        self.document.present_grid(image_ids)
        self._document_navigation.synchronize_projection()

    def _activate_workspace_target(self, composition_id: UUID) -> None:
        """Forward one document-grid activation to existing Output navigation signals."""

        image_id = self.document.image_id_for_composition(composition_id)
        if image_id is None:
            return
        self._document_navigation.activate_grid_target(image_id)

    def _handle_workspace_presentation_change(self, presentation: object) -> None:
        """Forward public CuteCanvas divider changes to persisted compare state."""

        from cutecanvas import CanvasPresentation

        if isinstance(presentation, CanvasPresentation):
            self._document_navigation.handle_workspace_presentation(presentation)


def _visible_sources(
    projection: OutputCanvasProjection,
) -> tuple[OutputCanvasSourceGroup, ...]:
    """Return source groups selected by the active scene context."""

    if projection.scene_count <= 1 or projection.active_scene_key is None:
        return projection.sources
    scene = next(
        (
            scene
            for scene in projection.scene_groups
            if scene.scene_key == projection.active_scene_key
        ),
        None,
    )
    return projection.sources if scene is None else scene.sources


def _source_image_ids(source: OutputCanvasSourceGroup) -> tuple[UUID, ...]:
    """Return ordered image identities for one source-grid presentation."""

    return tuple(item.image_id for _index, item in sorted(source.images_by_set.items()))


def _scene_overview_image_ids(
    projection: OutputCanvasProjection | None,
    *,
    preview_scenes: Mapping[str, object] | None = None,
) -> tuple[UUID, ...]:
    """Return ordered final or live-preview representatives for one scene overview."""

    preview_by_key = preview_scenes or {}
    image_ids: list[UUID] = []
    final_scene_keys: set[str] = set()
    if projection is not None:
        for scene in projection.scene_groups:
            final_scene_keys.add(scene.scene_key)
            preview = preview_by_key.get(scene.scene_key)
            preview_id = getattr(preview, "preview_image_id", None)
            image_id = preview_id or scene.primary_image_id
            if isinstance(image_id, UUID):
                image_ids.append(image_id)
    for scene_key, preview in sorted(
        preview_by_key.items(),
        key=lambda item: int(getattr(item[1], "order", 0)),
    ):
        if scene_key in final_scene_keys:
            continue
        preview_id = getattr(preview, "preview_image_id", None)
        if isinstance(preview_id, UUID):
            image_ids.append(preview_id)
    return tuple(dict.fromkeys(image_ids))


__all__ = ["OutputCanvas"]
