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

"""Compose prompt projection owners that govern interactive caret input."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtWidgets import QWidget

from ..core.editing.session import PromptEditingSession
from ..core.projection.caret import PromptProjectionSelection
from ..interactions import PromptSurfaceMouseHandler, PromptSurfaceMouseHost
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .caret_publication_owner import PromptProjectionCaretPublicationOwner
from .caret_state_owner import PromptProjectionCaretStateOwner
from .exact_weight_editor import PromptExactWeightEditor, PromptExactWeightEditorHost
from .focus_owner import PromptProjectionFocusOwner
from .frame_state import PromptProjectionEditorState
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .session import PromptProjectionSession
from .surface_graph_effects import PromptProjectionSurfaceGraphEffects
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .undo_payload import PromptProjectionUndoPayload


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceInteractionBindings:
    """Declare dependencies for the interactive pre-source owner graph."""

    surface: QWidget
    exact_weight_host: PromptExactWeightEditorHost
    mouse_host: PromptSurfaceMouseHost
    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    editor_state: PromptProjectionEditorState
    caret_state: PromptProjectionCaretStateOwner
    transient_overlays: PromptProjectionTransientEditOverlayController
    session: PromptProjectionSession
    layout: PromptLayoutEditToFrameCoordinator
    graph_effects: PromptProjectionSurfaceGraphEffects
    scroll_offset: Callable[[], float]
    selection: Callable[[], PromptProjectionSelection]
    collapse_expanded_token: Callable[[], None]
    emit_cursor_position_changed: Callable[[], None]
    flush_pending_projection: Callable[[str], None]
    request_update: Callable[[], None]
    surface_state: Callable[[], dict[str, object]]
    request_lora_context_menu: Callable[[QPointF, QPoint], bool]


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceInteractionRuntime:
    """Expose the owners that coordinate caret-centered surface interaction."""

    exact_weight: PromptExactWeightEditor
    caret_geometry: PromptProjectionCaretGeometryOwner
    caret_publication: PromptProjectionCaretPublicationOwner
    autocomplete_preview: PromptAutocompletePreviewProjectionOwner
    focus: PromptProjectionFocusOwner
    mouse: PromptSurfaceMouseHandler


def build_prompt_projection_surface_interaction_runtime(
    bindings: PromptProjectionSurfaceInteractionBindings,
) -> PromptProjectionSurfaceInteractionRuntime:
    """Build interactive owners in dependency order around the graph effect port."""

    graph_effects = bindings.graph_effects
    exact_weight = PromptExactWeightEditor(
        bindings.exact_weight_host,
        rebuild_projection=graph_effects.rebuild_projection,
    )
    caret_geometry = PromptProjectionCaretGeometryOwner(
        state=bindings.caret_state,
        editor_state=bindings.editor_state,
        overlays=bindings.transient_overlays,
        freshness_is_stale_safe=graph_effects.projection_is_stale,
        cursor_position=lambda: bindings.editing_session.cursor_position,
        anchor_position=lambda: bindings.editing_session.anchor_position,
        committed_document_rect=(
            lambda state: bindings.layout.frame.geometry.caret.cursor_rect(
                state,
                scroll_offset=0.0,
            )
        ),
        scroll_offset=bindings.scroll_offset,
    )
    caret_publication = PromptProjectionCaretPublicationOwner(
        state=bindings.caret_state,
        editor_state=bindings.editor_state,
        editing_session=bindings.editing_session,
        selection=bindings.selection,
        current_caret_rect=caret_geometry.current_viewport_rect,
        clear_transient_geometry=caret_geometry.clear_transient,
        expanded_source_range_present=(
            lambda: bindings.session.expanded_source_range is not None
        ),
        collapse_expanded_token=bindings.collapse_expanded_token,
        reconcile_autocomplete=graph_effects.reconcile_autocomplete,
        refresh_active_projection=graph_effects.refresh_active_projection,
        ensure_caret_visible=graph_effects.ensure_caret_visible,
        refresh_caret_layers=graph_effects.refresh_caret_layers,
        refresh_deferred_caret_layers=graph_effects.refresh_deferred_caret_layers,
        restart_caret_blink=graph_effects.restart_caret_blink,
        request_viewport_update=bindings.request_update,
        update_caret_paint=graph_effects.update_caret_paint,
        emit_cursor_position_changed=bindings.emit_cursor_position_changed,
        surface_state=bindings.surface_state,
    )
    autocomplete_preview = PromptAutocompletePreviewProjectionOwner(
        session=bindings.session,
        flush_pending_projection=(
            lambda: bindings.flush_pending_projection("autocomplete_preview")
        ),
        base_projection_is_stale=graph_effects.projection_is_stale,
        rebuild_base_projection=graph_effects.rebuild_projection,
        rebuild_active_projection=graph_effects.rebuild_active_projection,
        request_repaint=bindings.request_update,
        surface_state=bindings.surface_state,
    )
    focus = PromptProjectionFocusOwner(
        surface=bindings.surface,
        prepare_source_line_chrome=graph_effects.prepare_focus_chrome,
        schedule_caret_blink=graph_effects.schedule_caret_blink,
        parent=bindings.surface,
    )
    mouse = PromptSurfaceMouseHandler(
        bindings.mouse_host,
        caret_publication=caret_publication,
        caret_geometry=caret_geometry,
        rebuild_projection=graph_effects.rebuild_projection,
        ensure_pointer_focus=focus.ensure_pointer_focus,
        clear_autocomplete_preview=autocomplete_preview.clear_preview_state,
        request_lora_context_menu=bindings.request_lora_context_menu,
    )
    return PromptProjectionSurfaceInteractionRuntime(
        exact_weight=exact_weight,
        caret_geometry=caret_geometry,
        caret_publication=caret_publication,
        autocomplete_preview=autocomplete_preview,
        focus=focus,
        mouse=mouse,
    )


__all__ = [
    "PromptProjectionSurfaceInteractionBindings",
    "PromptProjectionSurfaceInteractionRuntime",
    "build_prompt_projection_surface_interaction_runtime",
]
