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

"""Compose the complete prompt projection surface owner graph."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QAbstractScrollArea, QScrollBar

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)

from ..core.editing.session import PromptEditingSession
from ..core.projection.caret import PromptProjectionSelection
from ..core.projection.tokens import PromptProjectionToken
from ..interactions import (
    PromptSurfaceKeyHost,
    PromptSurfaceMouseHost,
    PromptSurfaceWheelHost,
)
from ..interactions.deletion_controller import (
    PromptDeletionContextProvider,
    PromptDeletionProjectionEffects,
)
from ..interactions.external_text_input import PromptExternalTextInsertion
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .deferred_feedback_strategy import PromptDeferredFeedbackContext
from .caret_movement_controller import PromptProjectionCaretMovementHost
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .edit_publication import PromptEditPublicationSink
from .editing_runtime import PromptProjectionEditingRuntimeFactory
from .exact_weight_editor import PromptExactWeightEditorHost
from .geometry_reuse_warmer import PromptProjectionGeometryReuseWarmer
from .freshness_controller import PromptProjectionFreshnessBlockers
from .input_method_controller import PromptInputMethodHost
from .lora_surface_features import (
    PromptSurfaceLoraFeatureHost,
    PromptSurfaceLoraThumbnailPreloader,
)
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
from .surface_diagnostic_runtime import (
    PromptProjectionSurfaceDiagnosticBindings,
    build_prompt_projection_surface_diagnostics,
)
from .surface_foundation import (
    PromptProjectionSurfaceFoundation,
    PromptProjectionSurfaceFoundationBindings,
    build_prompt_projection_surface_foundation,
)
from .surface_graph_effects import (
    PromptProjectionSurfaceGraphEffects,
    bind_prompt_projection_surface_graph_effects,
)
from .surface_input_runtime import (
    PromptProjectionSurfaceInputBindings,
    PromptProjectionSurfaceInputRuntime,
    build_prompt_projection_surface_input_runtime,
)
from .surface_interaction_runtime import (
    PromptProjectionSurfaceInteractionBindings,
    PromptProjectionSurfaceInteractionRuntime,
    build_prompt_projection_surface_interaction_runtime,
)
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
from .undo_payload import PromptProjectionUndoPayload

THost = TypeVar("THost")


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceCompositionBindings(Generic[THost]):
    """Declare host ports required to compose the complete projection graph."""

    surface: QAbstractScrollArea
    editing_runtime_host: THost
    editing_runtime_factory: PromptProjectionEditingRuntimeFactory[
        THost,
        PromptProjectionUndoPayload,
    ]
    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    document_semantics: PromptDocumentSemantics | None
    lora_thumbnail_cache: PromptLoraThumbnailCache | None
    lora_thumbnail_preloader: PromptSurfaceLoraThumbnailPreloader | None
    lora_feature_host: PromptSurfaceLoraFeatureHost
    exact_weight_host: PromptExactWeightEditorHost
    mouse_host: PromptSurfaceMouseHost
    input_method_host: PromptInputMethodHost
    deletion_context_provider: PromptDeletionContextProvider
    deletion_projection_effects: PromptDeletionProjectionEffects
    key_host: PromptSurfaceKeyHost
    wheel_host: PromptSurfaceWheelHost
    publication_sink: PromptEditPublicationSink
    build_context: PromptProjectionBuildContext
    deferred_feedback_context: PromptDeferredFeedbackContext
    prompt_state_host: PromptProjectionPromptStateHost
    fact_context: PromptSourceEditProjectionFactContext
    source_presentation_sink: PromptSourceCommitPresentationSink
    caret_movement_host: PromptProjectionCaretMovementHost
    set_cursor_positions: Callable[[int, int], object]
    publish_thumbnail_media: Callable[[str], None]
    publish_context_menu: Callable[[PromptProjectionToken, QPoint], None]
    publish_undo_available: Callable[[bool], None]
    publish_redo_available: Callable[[bool], None]
    external_text_insertion: PromptExternalTextInsertion
    finish_pending_key_edit_block: Callable[[str], None]
    collapse_expanded_token: Callable[[], None]
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
    apply_accent_paint_state: Callable[[], None]
    live_source_text: Callable[[], str]
    viewport_rect: Callable[[], QRectF]
    cursor_position: Callable[[], int]
    decoration_accent_ranges: Callable[[], tuple[tuple[int, int], ...]]
    cancel_pending_projection: Callable[[], None]
    font: Callable[[], QFont]
    palette: Callable[[], QPalette]
    content_height_sink: Callable[[float], None]
    invalidate_backing: Callable[[QRect], None]
    emit_cursor_position_changed: Callable[[], None]
    request_update: Callable[[], None]
    input_method_hints: Callable[[], Qt.InputMethodHint]
    surface_state: Callable[[], dict[str, object]]


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceCompositionRuntime:
    """Expose the complete projection graph to the mounted Qt adapter."""

    foundation: PromptProjectionSurfaceFoundation
    interaction: PromptProjectionSurfaceInteractionRuntime
    diagnostics: PromptDiagnosticLayerOwner
    input_runtime: PromptProjectionSurfaceInputRuntime
    geometry_reuse_warmer: PromptProjectionGeometryReuseWarmer
    source: PromptProjectionSourceStateOwners
    lifecycle: PromptProjectionSurfaceLifecycleRuntime
    presentation: PromptProjectionSurfacePresentationRuntime


def build_prompt_projection_surface_composition_runtime(
    bindings: PromptProjectionSurfaceCompositionBindings[THost],
) -> PromptProjectionSurfaceCompositionRuntime:
    """Compose and bind the complete projection-surface owner graph."""

    surface = bindings.surface
    viewport = surface.viewport()
    foundation = build_prompt_projection_surface_foundation(
        PromptProjectionSurfaceFoundationBindings(
            host=bindings.lora_feature_host,
            editing_session=bindings.editing_session,
            document_semantics=bindings.document_semantics,
            lora_thumbnail_cache=bindings.lora_thumbnail_cache,
            lora_thumbnail_preloader=bindings.lora_thumbnail_preloader,
            publish_thumbnail_media=bindings.publish_thumbnail_media,
            publish_context_menu=bindings.publish_context_menu,
        )
    )
    graph_effects = PromptProjectionSurfaceGraphEffects()
    interaction = build_prompt_projection_surface_interaction_runtime(
        PromptProjectionSurfaceInteractionBindings(
            surface=surface,
            exact_weight_host=bindings.exact_weight_host,
            mouse_host=bindings.mouse_host,
            editing_session=bindings.editing_session,
            editor_state=foundation.editor_state,
            caret_state=foundation.caret_state,
            transient_overlays=foundation.transient_overlays,
            session=foundation.session,
            layout=foundation.layout,
            graph_effects=graph_effects,
            scroll_offset=bindings.scroll_offset,
            selection=bindings.selection,
            collapse_expanded_token=bindings.collapse_expanded_token,
            emit_cursor_position_changed=bindings.emit_cursor_position_changed,
            flush_pending_projection=bindings.flush_pending_projection,
            request_update=bindings.request_update,
            surface_state=bindings.surface_state,
            request_lora_context_menu=foundation.lora_features.request_context_menu,
        )
    )
    diagnostics = build_prompt_projection_surface_diagnostics(
        PromptProjectionSurfaceDiagnosticBindings(
            parent=surface,
            viewport=viewport,
            session=foundation.session,
            layout=foundation.layout,
            frame_state=foundation.frame_state,
            graph_effects=graph_effects,
            selection=bindings.selection,
            scroll_offset=bindings.scroll_offset,
            is_alive=bindings.is_available,
        )
    )
    input_runtime = build_prompt_projection_surface_input_runtime(
        PromptProjectionSurfaceInputBindings(
            input_method_host=bindings.input_method_host,
            deletion_context_provider=bindings.deletion_context_provider,
            deletion_projection_effects=bindings.deletion_projection_effects,
            key_host=bindings.key_host,
            wheel_host=bindings.wheel_host,
            editing_runtime_host=bindings.editing_runtime_host,
            editing_runtime_factory=bindings.editing_runtime_factory,
            editing_session=bindings.editing_session,
            caret_state=foundation.caret_state,
            projection_session=foundation.session,
            editor_state=foundation.editor_state,
            viewport=viewport,
            layout=foundation.layout,
            mouse=interaction.mouse,
            set_cursor_positions=bindings.set_cursor_positions,
            publish_undo_available=bindings.publish_undo_available,
            publish_redo_available=bindings.publish_redo_available,
            external_text_insertion=bindings.external_text_insertion,
            finish_pending_key_edit_block=bindings.finish_pending_key_edit_block,
            publish_render_frame=bindings.publish_render_frame,
            request_update=bindings.request_update,
            input_method_hints=bindings.input_method_hints,
            viewport_rect=bindings.viewport_rect,
            parent=surface,
        )
    )
    geometry_reuse_warmer = PromptProjectionGeometryReuseWarmer(
        is_available=bindings.is_available,
        is_projected=graph_effects.is_projected,
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
            diagnostics=diagnostics,
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
            is_projected=graph_effects.is_projected,
            tokens=lambda: foundation.editor_state.projection.document.tokens,
            apply_session_paint_state=graph_effects.apply_session_paint_state,
            apply_accent_paint_state=bindings.apply_accent_paint_state,
            rebuild_projection=graph_effects.rebuild_projection,
            publish_caret=(
                lambda cursor_state, anchor_state: (
                    interaction.caret_publication.publish(
                        cursor_state=cursor_state,
                        anchor_state=anchor_state,
                    )
                )
            ),
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
            diagnostics=diagnostics,
            transient_overlays=foundation.transient_overlays,
            reorder=lifecycle.reorder,
            caret_state=foundation.caret_state,
            caret_publication=interaction.caret_publication,
            caret_geometry=interaction.caret_geometry,
            live_source_text=bindings.live_source_text,
            viewport_rect=bindings.viewport_rect,
            scroll_offset=bindings.scroll_offset,
            cursor_position=bindings.cursor_position,
            focus_active=interaction.focus.focus_owner_has_focus,
            selection=bindings.selection,
            active_span_range=bindings.active_span_range,
            decoration_accent_ranges=bindings.decoration_accent_ranges,
            flush_pending_projection=bindings.flush_pending_projection,
            cancel_pending_projection=bindings.cancel_pending_projection,
            clear_hovered_token=(
                lambda: interaction.mouse.clear_hovered_token(update=False)
            ),
            hovered_token_id=lambda: interaction.mouse.hovered_token_id,
            prewarm_visible_banners=(
                lambda: foundation.lora_features.prewarm_visible_banners(
                    foundation.layout.frame.geometry
                )
            ),
            font=bindings.font,
            palette=bindings.palette,
            should_paint_caret=lifecycle.caret_visual.should_paint_caret,
            current_caret_rect=interaction.caret_geometry.current_viewport_rect,
            scroll_range_sink=(
                lambda page_step, scroll_range: (
                    input_runtime.wheel.sync_external_scroll_range(
                        page_step=page_step,
                        scroll_range=scroll_range,
                    )
                )
            ),
            content_height_sink=bindings.content_height_sink,
            invalidate_backing=bindings.invalidate_backing,
            ensure_caret_visible=lifecycle.caret_visual.ensure_caret_visible,
            emit_cursor_position_changed=bindings.emit_cursor_position_changed,
            request_update=bindings.request_update,
            surface_state=bindings.surface_state,
        )
    )
    bind_prompt_projection_surface_graph_effects(
        graph_effects,
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
        foundation=foundation,
        interaction=interaction,
        diagnostics=diagnostics,
        input_runtime=input_runtime,
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
