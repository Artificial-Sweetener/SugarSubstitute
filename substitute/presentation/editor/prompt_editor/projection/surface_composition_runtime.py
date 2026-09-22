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

"""Compose the source, lifecycle, and presentation projection owner graph."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QScrollBar

from ..core.projection.caret import (
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from ..core.projection.tokens import PromptProjectionToken
from .deferred_feedback_strategy import PromptDeferredFeedbackContext
from .caret_movement_controller import PromptProjectionCaretMovementHost
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .edit_publication import PromptEditPublicationSink
from .geometry_reuse_warmer import PromptProjectionGeometryReuseWarmer
from .freshness_controller import PromptProjectionFreshnessBlockers
from .projection_build_context import PromptProjectionBuildContext
from .prompt_state_applier import PromptProjectionPromptStateHost
from .source_commit_ports import PromptSourceCommitPresentationSink
from .source_edit_projection_facts import PromptSourceEditProjectionFactContext
from .source_lifecycle_effects import (
    PromptProjectionSourceLifecycleEffects,
    bind_prompt_projection_source_lifecycle_effects,
)
from .source_state_wiring import (
    PromptProjectionSourceStateBindings,
    PromptProjectionSourceStateOwners,
    build_prompt_projection_source_state_owners,
)
from .surface_foundation import PromptProjectionSurfaceFoundation
from .surface_graph_effects import (
    PromptProjectionSurfaceGraphEffects,
    bind_prompt_projection_surface_graph_effects,
)
from .surface_input_runtime import PromptProjectionSurfaceInputRuntime
from .surface_interaction_runtime import PromptProjectionSurfaceInteractionRuntime
from .surface_lifecycle_runtime import (
    PromptProjectionSurfaceLifecycleBindings,
    PromptProjectionSurfaceLifecycleRuntime,
    build_prompt_projection_surface_lifecycle_runtime,
)
from .surface_presentation_runtime import (
    PromptProjectionSurfacePresentationBindings,
    PromptProjectionSurfacePresentationRuntime,
    build_prompt_projection_surface_presentation_runtime,
)


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceCompositionBindings:
    """Declare host ports required to compose the complete projection graph."""

    surface: QAbstractScrollArea
    foundation: PromptProjectionSurfaceFoundation
    interaction: PromptProjectionSurfaceInteractionRuntime
    input_runtime: PromptProjectionSurfaceInputRuntime
    diagnostics: PromptDiagnosticLayerOwner
    graph_effects: PromptProjectionSurfaceGraphEffects
    publication_sink: PromptEditPublicationSink
    build_context: PromptProjectionBuildContext
    deferred_feedback_context: PromptDeferredFeedbackContext
    prompt_state_host: PromptProjectionPromptStateHost
    fact_context: PromptSourceEditProjectionFactContext
    source_presentation_sink: PromptSourceCommitPresentationSink
    caret_movement_host: PromptProjectionCaretMovementHost
    set_cursor_positions: Callable[[int, int], object]
    active_span_range: Callable[[], tuple[int, int] | None]
    projection_freshness_blockers: Callable[[], PromptProjectionFreshnessBlockers]
    is_available: Callable[[], bool]
    scroll_offset: Callable[[], float]
    publish_render_frame: Callable[[], None]
    flush_pending_projection: Callable[[str], None]
    synchronize_layout: Callable[[], None]
    selection: Callable[[], PromptProjectionSelection]
    surface_is_visible: Callable[[], bool]
    visible_scroll_bar: Callable[[], QScrollBar]
    tokens: Callable[[], Sequence[PromptProjectionToken]]
    apply_accent_paint_state: Callable[[], None]
    publish_caret: Callable[
        [PromptProjectionCaretState, PromptProjectionCaretState], None
    ]
    live_source_text: Callable[[], str]
    viewport_rect: Callable[[], QRectF]
    cursor_position: Callable[[], int]
    focus_active: Callable[[], bool]
    decoration_accent_ranges: Callable[[], tuple[tuple[int, int], ...]]
    cancel_pending_projection: Callable[[], None]
    prewarm_visible_banners: Callable[[], object]
    font: Callable[[], QFont]
    palette: Callable[[], QPalette]
    scroll_range_sink: Callable[[int, int], None]
    content_height_sink: Callable[[float], None]
    invalidate_backing: Callable[[QRect], None]
    emit_cursor_position_changed: Callable[[], None]
    request_update: Callable[[], None]
    surface_state: Callable[[], dict[str, object]]


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceCompositionRuntime:
    """Expose the complete late projection graph and its warmup owner."""

    geometry_reuse_warmer: PromptProjectionGeometryReuseWarmer
    source: PromptProjectionSourceStateOwners
    lifecycle: PromptProjectionSurfaceLifecycleRuntime
    presentation: PromptProjectionSurfacePresentationRuntime


def build_prompt_projection_surface_composition_runtime(
    bindings: PromptProjectionSurfaceCompositionBindings,
) -> PromptProjectionSurfaceCompositionRuntime:
    """Compose and bind the complete late projection owner graph."""

    foundation = bindings.foundation
    interaction = bindings.interaction
    input_runtime = bindings.input_runtime
    surface = bindings.surface
    viewport = surface.viewport()
    geometry_reuse_warmer = PromptProjectionGeometryReuseWarmer(
        is_available=bindings.is_available,
        is_projected=bindings.graph_effects.is_projected,
        prewarm=(
            lambda: (
                foundation.layout.frame.output.snapshot.prewarm_inline_object_fragment_index()
            )
        ),
        parent=surface,
    )
    source_lifecycle_effects = PromptProjectionSourceLifecycleEffects()
    source = build_prompt_projection_source_state_owners(
        PromptProjectionSourceStateBindings(
            applicator=foundation.applicator,
            editor_state=foundation.editor_state,
            layout=foundation.layout,
            source_line_chrome=foundation.source_line_chrome,
            session=foundation.session,
            pointer_sink=interaction.mouse,
            publication_sink=bindings.publication_sink,
            build_context=bindings.build_context,
            deferred_feedback_context=bindings.deferred_feedback_context,
            prompt_state_host=bindings.prompt_state_host,
            fact_context=bindings.fact_context,
            source_presentation_sink=bindings.source_presentation_sink,
            caret_publication=interaction.caret_publication,
            caret_geometry=interaction.caret_geometry,
            transient_edit_overlays=foundation.transient_overlays,
            set_cursor_positions=bindings.set_cursor_positions,
            active_span_range=bindings.active_span_range,
            lifecycle_effects=source_lifecycle_effects,
            projection_freshness_blockers=bindings.projection_freshness_blockers,
            input_method_source_changed=input_runtime.input_method.source_changed,
            document_scroll_bar=surface.verticalScrollBar(),
            schedule_geometry_reuse_warm=(
                lambda reason: geometry_reuse_warmer.schedule(reason=reason)
            ),
            diagnostics=bindings.diagnostics,
            autocomplete_preview=interaction.autocomplete_preview,
            transient_viewport=viewport,
            transient_scroll_offset=bindings.scroll_offset,
            transient_publish_render_frame=bindings.publish_render_frame,
        ),
        parent=surface,
        frame_state=foundation.frame_state,
    )
    lifecycle = build_prompt_projection_surface_lifecycle_runtime(
        PromptProjectionSurfaceLifecycleBindings(
            surface=surface,
            viewport=viewport,
            applicator=foundation.applicator,
            thumbnail_cache=foundation.thumbnail_cache,
            editor_state=foundation.editor_state,
            layout=foundation.layout,
            freshness=source.freshness_controller,
            caret_state=foundation.caret_state,
            caret_publication=interaction.caret_publication,
            caret_geometry=interaction.caret_geometry,
            caret_movement_host=bindings.caret_movement_host,
            focus=interaction.focus,
            session=foundation.session,
            scroll_offset=bindings.scroll_offset,
            flush_pending_projection=bindings.flush_pending_projection,
            synchronize_layout=bindings.synchronize_layout,
            publish_render_frame=bindings.publish_render_frame,
            request_update=bindings.request_update,
            selection=bindings.selection,
            surface_is_visible=bindings.surface_is_visible,
            visible_scroll_bar=bindings.visible_scroll_bar,
            is_projected=bindings.graph_effects.is_projected,
            tokens=bindings.tokens,
            apply_session_paint_state=bindings.graph_effects.apply_session_paint_state,
            apply_accent_paint_state=bindings.apply_accent_paint_state,
            rebuild_projection=bindings.graph_effects.rebuild_projection,
            publish_caret=bindings.publish_caret,
            parent=surface,
        )
    )
    presentation = build_prompt_projection_surface_presentation_runtime(
        PromptProjectionSurfacePresentationBindings(
            surface=surface,
            viewport=viewport,
            applicator=foundation.applicator,
            editor_state=foundation.editor_state,
            session=foundation.session,
            layout=foundation.layout,
            frame_state=foundation.frame_state,
            freshness=source.freshness_controller,
            width_resolver=lifecycle.layout_width,
            source_document=source.source_document,
            source_line_chrome=foundation.source_line_chrome,
            search_highlight=foundation.search_highlight,
            input_method=input_runtime.input_method,
            content_media=foundation.content_media,
            selection_layer=lifecycle.selection_layer,
            diagnostics=bindings.diagnostics,
            transient_overlays=foundation.transient_overlays,
            reorder=lifecycle.reorder,
            caret_state=foundation.caret_state,
            caret_publication=interaction.caret_publication,
            caret_geometry=interaction.caret_geometry,
            live_source_text=bindings.live_source_text,
            viewport_rect=bindings.viewport_rect,
            scroll_offset=bindings.scroll_offset,
            cursor_position=bindings.cursor_position,
            focus_active=bindings.focus_active,
            selection=bindings.selection,
            active_span_range=bindings.active_span_range,
            decoration_accent_ranges=bindings.decoration_accent_ranges,
            flush_pending_projection=bindings.flush_pending_projection,
            cancel_pending_projection=bindings.cancel_pending_projection,
            clear_hovered_token=(
                lambda: interaction.mouse.clear_hovered_token(update=False)
            ),
            hovered_token_id=lambda: interaction.mouse.hovered_token_id,
            prewarm_visible_banners=bindings.prewarm_visible_banners,
            font=bindings.font,
            palette=bindings.palette,
            should_paint_caret=lifecycle.caret_visual.should_paint_caret,
            current_caret_rect=interaction.caret_geometry.current_viewport_rect,
            scroll_range_sink=bindings.scroll_range_sink,
            content_height_sink=bindings.content_height_sink,
            invalidate_backing=bindings.invalidate_backing,
            ensure_caret_visible=lifecycle.caret_visual.ensure_caret_visible,
            emit_cursor_position_changed=bindings.emit_cursor_position_changed,
            request_update=bindings.request_update,
            surface_state=bindings.surface_state,
        )
    )
    bind_prompt_projection_surface_graph_effects(
        bindings.graph_effects,
        freshness=source.freshness_controller,
        autocomplete=interaction.autocomplete_preview,
        lifecycle=lifecycle,
        presentation=presentation,
    )
    bind_prompt_projection_source_lifecycle_effects(
        source_lifecycle_effects,
        lifecycle=lifecycle,
        presentation=presentation,
    )
    return PromptProjectionSurfaceCompositionRuntime(
        geometry_reuse_warmer=geometry_reuse_warmer,
        source=source,
        lifecycle=lifecycle,
        presentation=presentation,
    )


__all__ = [
    "PromptProjectionSurfaceCompositionBindings",
    "PromptProjectionSurfaceCompositionRuntime",
    "build_prompt_projection_surface_composition_runtime",
]
