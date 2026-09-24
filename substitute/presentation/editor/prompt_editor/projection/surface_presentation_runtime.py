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

"""Compose the late-bound projection presentation runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QWidget

from ..core.projection.caret import PromptProjectionSelection
from ..interactions.pointer_ports import PromptSurfacePointerInteractions
from .active_projection_owner import PromptActiveProjectionOwner
from .applicator import PromptProjectionApplicator
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .caret_publication_owner import PromptProjectionCaretPublicationOwner
from .caret_state_owner import PromptProjectionCaretStateOwner
from .content_media_owner import PromptProjectionContentMediaOwner
from .content_selection_owner import PromptProjectionSelectionLayerOwner
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .fill_band_owner import PromptProjectionFillBandOwner
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionFrameStatePublisher,
    PromptProjectionLayoutWidthResolver,
)
from .frame_synchronizer import PromptProjectionFrameSynchronizer
from .freshness_controller import PromptProjectionFreshnessController
from .input_method_controller import PromptInputMethodController
from .layout_publication_owner import PromptProjectionLayoutPublicationOwner
from .presentation_query_owner import PromptProjectionPresentationQueryOwner
from .rebuild_owner import PromptProjectionRebuildOwner
from .region_chrome_presentation import PromptRegionChromePresentationOwner
from .render_compositor import PromptProjectionRenderCompositor
from .render_frame_owner import PromptProjectionRenderFrameOwner
from .render_publication_owner import PromptProjectionRenderPublicationOwner
from .reorder_geometry import reorder_geometry_state
from .reorder_projection_owner import PromptReorderProjectionOwner
from .scene_diagnostics_owner import PromptSceneDiagnosticsOwner
from .search_highlight_owner import PromptSearchHighlightLayerOwner
from .search_presentation_owner import PromptSearchPresentationOwner
from .session import PromptProjectionSession
from .source_document import PromptProjectionSourceDocument
from .source_line_chrome import PromptSourceLineChrome
from .source_line_presentation_owner import PromptSourceLinePresentationOwner
from .theme import semantic_palette_from_theme
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfacePresentationBindings:
    """Declare stable collaborators and host effects required by presentation."""

    surface: QAbstractScrollArea
    viewport: QWidget
    applicator: PromptProjectionApplicator
    editor_state: PromptProjectionEditorState
    session: PromptProjectionSession
    layout: PromptLayoutEditToFrameCoordinator
    frame_state: PromptProjectionFrameStatePublisher
    freshness: PromptProjectionFreshnessController
    width_resolver: PromptProjectionLayoutWidthResolver
    source_document: PromptProjectionSourceDocument
    source_line_chrome: PromptSourceLineChrome
    search_highlight: PromptSearchHighlightLayerOwner
    input_method: PromptInputMethodController
    content_media: PromptProjectionContentMediaOwner
    selection_layer: PromptProjectionSelectionLayerOwner
    diagnostics: PromptDiagnosticLayerOwner
    transient_overlays: PromptProjectionTransientEditOverlayController
    reorder: PromptReorderProjectionOwner
    caret_state: PromptProjectionCaretStateOwner
    caret_publication: PromptProjectionCaretPublicationOwner
    caret_geometry: PromptProjectionCaretGeometryOwner
    live_source_text: Callable[[], str]
    viewport_rect: Callable[[], QRectF]
    scroll_offset: Callable[[], float]
    cursor_position: Callable[[], int]
    focus_active: Callable[[], bool]
    selection: Callable[[], PromptProjectionSelection]
    active_span_range: Callable[[], tuple[int, int] | None]
    decoration_accent_ranges: Callable[[], tuple[tuple[int, int], ...]]
    flush_pending_projection: Callable[[str], None]
    cancel_pending_projection: Callable[[], None]
    clear_hovered_token: Callable[[], None]
    hovered_token_id: Callable[[], str | None]
    prewarm_visible_banners: Callable[[], object]
    font: Callable[[], QFont]
    palette: Callable[[], QPalette]
    should_paint_caret: Callable[[], bool]
    current_caret_rect: Callable[[], QRectF]
    scroll_range_sink: Callable[[int, int], None]
    content_height_sink: Callable[[float], None]
    invalidate_backing: Callable[[QRect], None]
    ensure_caret_visible: Callable[[], None]
    emit_cursor_position_changed: Callable[[], None]
    request_update: Callable[[], None]
    surface_state: Callable[[], dict[str, object]]


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfacePresentationRuntime:
    """Expose the composed owners used by the Qt projection surface."""

    fill_bands: PromptProjectionFillBandOwner
    pointer_interactions: PromptSurfacePointerInteractions
    region_chrome: PromptRegionChromePresentationOwner
    render_frame: PromptProjectionRenderFrameOwner
    render_publication: PromptProjectionRenderPublicationOwner
    render_compositor: PromptProjectionRenderCompositor
    frame_synchronizer: PromptProjectionFrameSynchronizer
    layout_publication: PromptProjectionLayoutPublicationOwner
    scene_diagnostics: PromptSceneDiagnosticsOwner
    search: PromptSearchPresentationOwner
    source_line: PromptSourceLinePresentationOwner
    active_projection: PromptActiveProjectionOwner
    queries: PromptProjectionPresentationQueryOwner
    rebuild: PromptProjectionRebuildOwner


def build_prompt_projection_surface_presentation_runtime(
    bindings: PromptProjectionSurfacePresentationBindings,
) -> PromptProjectionSurfacePresentationRuntime:
    """Compose presentation owners in dependency order without surface-owned state."""

    projection_rebuild: PromptProjectionRebuildOwner
    active_projection: PromptActiveProjectionOwner
    render_publication: PromptProjectionRenderPublicationOwner

    def publish_render_frame() -> None:
        """Publish through the owner installed later in composition order."""

        render_publication.publish()

    fill_bands = PromptProjectionFillBandOwner(
        freshness=bindings.freshness,
        display_mode=lambda: projection_rebuild.display_mode,
        current_source_identity=lambda: bindings.editor_state.source_identity,
        committed_source_text=lambda: (
            bindings.editor_state.projection.document.source_text
        ),
        live_source_text=bindings.live_source_text,
        viewport_rect=bindings.viewport_rect,
        scroll_offset=bindings.scroll_offset,
        content_width=lambda: (
            bindings.layout.frame.output.snapshot.content_size.width()
        ),
        content_left_inset=lambda: bindings.source_line_chrome.content_left_inset,
        reorder_geometry=bindings.reorder.geometry_owner.projection_geometry,
        geometry_state=lambda: reorder_geometry_state(bindings.layout.frame.geometry),
    )
    pointer_interactions = PromptSurfacePointerInteractions()
    region_chrome = PromptRegionChromePresentationOwner(
        publish_render_frame=publish_render_frame,
        request_update=bindings.request_update,
    )
    render_frame = PromptProjectionRenderFrameOwner()
    render_publication = PromptProjectionRenderPublicationOwner(
        surface=bindings.surface,
        viewport=bindings.viewport,
        layout=bindings.layout,
        editor_state=bindings.editor_state,
        session=bindings.session,
        reorder_preview=bindings.reorder.preview,
        input_method=bindings.input_method,
        content_media=bindings.content_media,
        selection_layer=bindings.selection_layer,
        source_line_chrome=bindings.source_line_chrome,
        region_chrome=region_chrome.chrome,
        reorder_visual_state=bindings.reorder.presentation.visual_state,
        search_highlight=bindings.search_highlight,
        diagnostics=bindings.diagnostics,
        transient_overlays=bindings.transient_overlays,
        freshness=bindings.freshness,
        frame_owner=render_frame,
        active_frame=lambda: bindings.reorder.active_frame,
        cursor_position=bindings.cursor_position,
        focus_active=bindings.focus_active,
        scroll_offset=bindings.scroll_offset,
        should_paint_caret=bindings.should_paint_caret,
        current_caret_rect=bindings.current_caret_rect,
        preview_visible_region=bindings.reorder.presentation.preview_visible_region,
        reorder_preview_generation=bindings.reorder.preview_generation,
    )
    render_compositor = PromptProjectionRenderCompositor()
    bindings.layout.frame.set_semantic_palette(semantic_palette_from_theme())
    frame_synchronizer = PromptProjectionFrameSynchronizer(
        host=bindings.surface,
        layout=bindings.layout,
        applicator=bindings.applicator,
        reorder_preview=bindings.reorder.preview,
        frame_state=bindings.frame_state,
        width_resolver=bindings.width_resolver,
        freshness=bindings.freshness,
        region_chrome=region_chrome.chrome,
        source_document=bindings.source_document,
        source_line_chrome=bindings.source_line_chrome,
        scroll_offset=bindings.scroll_offset,
        scroll_range_sink=bindings.scroll_range_sink,
        content_height_sink=bindings.content_height_sink,
    )
    layout_publication = PromptProjectionLayoutPublicationOwner(
        reorder=bindings.reorder,
        frame_synchronizer=frame_synchronizer,
        render_publication=render_publication,
        display_mode=lambda: projection_rebuild.display_mode,
    )
    scene_diagnostics = PromptSceneDiagnosticsOwner(
        flush_pending_projection=bindings.flush_pending_projection,
        clear_hovered_token=bindings.clear_hovered_token,
        rebuild_projection=lambda: projection_rebuild.rebuild(),
    )
    search = PromptSearchPresentationOwner(
        session=bindings.session,
        publish_changed=render_publication.search_changed,
        publish_cleared=render_publication.search_cleared,
        request_update=bindings.request_update,
    )
    source_line = PromptSourceLinePresentationOwner(
        chrome=bindings.source_line_chrome,
        flush_pending_projection=bindings.flush_pending_projection,
        synchronize_layout=layout_publication.sync,
        publish_configuration_changed=render_publication.source_line_configuration_changed,
        request_update=bindings.request_update,
    )
    active_projection = PromptActiveProjectionOwner(
        surface=bindings.surface,
        viewport=bindings.viewport,
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        session=bindings.session,
        layout=bindings.layout,
        frame_state=bindings.frame_state,
        freshness=bindings.freshness,
        caret_geometry=bindings.caret_geometry,
        display_mode=lambda: projection_rebuild.display_mode,
        selection=bindings.selection,
        cursor_position=bindings.cursor_position,
        reorder_active=bindings.reorder.is_active,
        active_span_range=bindings.active_span_range,
        decoration_accent_ranges=bindings.decoration_accent_ranges,
        scene_error_keys=lambda: scene_diagnostics.keys,
        synchronize_layout=(
            lambda commit: layout_publication.sync(commit_projection=commit)
        ),
        publish_render_frame=publish_render_frame,
        surface_state=bindings.surface_state,
    )
    queries = PromptProjectionPresentationQueryOwner(
        editor_state=bindings.editor_state,
        active_document=lambda: active_projection.document,
        layout=bindings.layout,
        freshness=bindings.freshness,
        source_line_chrome=bindings.source_line_chrome,
        fill_bands=fill_bands,
        reorder_preview=bindings.reorder.preview,
        flush_pending_projection=bindings.flush_pending_projection,
        viewport_rect=bindings.viewport_rect,
        scroll_offset=bindings.scroll_offset,
        cursor_position=bindings.cursor_position,
        hovered_token_id=bindings.hovered_token_id,
        focused_token_id=lambda: bindings.caret_state.cursor_state.token_id,
    )
    projection_rebuild = PromptProjectionRebuildOwner(
        surface=bindings.surface,
        viewport=bindings.viewport,
        applicator=bindings.applicator,
        editor_state=bindings.editor_state,
        session=bindings.session,
        layout=bindings.layout,
        caret_state=bindings.caret_state,
        caret_publication=bindings.caret_publication,
        caret_geometry=bindings.caret_geometry,
        render_publication=render_publication,
        flush_pending_projection=bindings.flush_pending_projection,
        cancel_pending_projection=bindings.cancel_pending_projection,
        decoration_accent_ranges=bindings.decoration_accent_ranges,
        scene_error_keys=lambda: scene_diagnostics.keys,
        font=bindings.font,
        palette=bindings.palette,
        clear_reorder=(
            lambda reason: bindings.reorder.clear_projection_and_geometry(reason=reason)
        ),
        clear_hovered_token=bindings.clear_hovered_token,
        publish_active_span_range=active_projection.publish_rendered_active_span_range,
        rebuild_active_projection=(
            lambda: active_projection.rebuild(commit_projection=True)
        ),
        prewarm_visible_banners=bindings.prewarm_visible_banners,
        invalidate_backing=bindings.invalidate_backing,
        ensure_caret_visible=bindings.ensure_caret_visible,
        emit_cursor_position_changed=bindings.emit_cursor_position_changed,
        active_projection_requires_layout=active_projection.requires_layout,
        restore_base_projection_layout=active_projection.restore_base_layout,
    )
    return PromptProjectionSurfacePresentationRuntime(
        fill_bands=fill_bands,
        pointer_interactions=pointer_interactions,
        region_chrome=region_chrome,
        render_frame=render_frame,
        render_publication=render_publication,
        render_compositor=render_compositor,
        frame_synchronizer=frame_synchronizer,
        layout_publication=layout_publication,
        scene_diagnostics=scene_diagnostics,
        search=search,
        source_line=source_line,
        active_projection=active_projection,
        queries=queries,
        rebuild=projection_rebuild,
    )


__all__ = [
    "PromptProjectionSurfacePresentationBindings",
    "PromptProjectionSurfacePresentationRuntime",
    "build_prompt_projection_surface_presentation_runtime",
]
