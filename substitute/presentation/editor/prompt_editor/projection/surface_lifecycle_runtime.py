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

"""Compose projection owners that depend on initialized source lifecycle state."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRectF
from PySide6.QtWidgets import QScrollBar, QWidget

from ..core.projection.caret import (
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from ..core.projection.tokens import PromptProjectionToken
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..qt_lifecycle import qt_object_is_alive
from .applicator import PromptProjectionApplicator
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .caret_movement_controller import (
    PromptProjectionCaretMovementController,
    PromptProjectionCaretMovementHost,
)
from .caret_publication_owner import PromptProjectionCaretPublicationOwner
from .caret_state_owner import PromptProjectionCaretStateOwner
from .caret_visual import PromptSurfaceCaretVisualController
from .content_selection_owner import PromptProjectionSelectionLayerOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .emphasis_projection_owner import PromptProjectionEmphasisOwner
from .focus_owner import PromptProjectionFocusOwner
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionLayoutWidthResolver,
)
from .freshness_controller import PromptProjectionFreshnessController
from .reorder_projection_owner import PromptReorderProjectionOwner
from .session import PromptProjectionSession


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceLifecycleBindings:
    """Declare source-ready dependencies required by projection lifecycle owners."""

    surface: QWidget
    viewport: QWidget
    applicator: PromptProjectionApplicator
    thumbnail_cache: PromptLoraThumbnailCache
    editor_state: PromptProjectionEditorState
    layout: PromptLayoutEditToFrameCoordinator
    freshness: PromptProjectionFreshnessController
    caret_state: PromptProjectionCaretStateOwner
    caret_publication: PromptProjectionCaretPublicationOwner
    caret_geometry: PromptProjectionCaretGeometryOwner
    caret_movement_host: PromptProjectionCaretMovementHost
    focus: PromptProjectionFocusOwner
    session: PromptProjectionSession
    scroll_offset: Callable[[], float]
    flush_pending_projection: Callable[[str], None]
    synchronize_layout: Callable[[], None]
    publish_render_frame: Callable[[], None]
    request_update: Callable[[], None]
    selection: Callable[[], PromptProjectionSelection]
    surface_is_visible: Callable[[], bool]
    visible_scroll_bar: Callable[[], QScrollBar]
    is_projected: Callable[[], bool]
    tokens: Callable[[], Sequence[PromptProjectionToken]]
    apply_session_paint_state: Callable[[], bool]
    apply_accent_paint_state: Callable[[], None]
    rebuild_projection: Callable[[], None]
    publish_caret: Callable[
        [PromptProjectionCaretState, PromptProjectionCaretState], None
    ]
    parent: QObject


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceLifecycleRuntime:
    """Expose source-ready projection lifecycle owners as one graph."""

    layout_width: PromptProjectionLayoutWidthResolver
    reorder: PromptReorderProjectionOwner
    selection_layer: PromptProjectionSelectionLayerOwner
    caret_visual: PromptSurfaceCaretVisualController
    emphasis: PromptProjectionEmphasisOwner
    caret_movement: PromptProjectionCaretMovementController


def build_prompt_projection_surface_lifecycle_runtime(
    bindings: PromptProjectionSurfaceLifecycleBindings,
) -> PromptProjectionSurfaceLifecycleRuntime:
    """Build source-ready projection lifecycle owners in dependency order."""

    layout_width = PromptProjectionLayoutWidthResolver(
        host=bindings.surface,
        viewport=bindings.viewport,
        freshness=bindings.freshness,
    )
    reorder = PromptReorderProjectionOwner(
        surface=bindings.surface,
        viewport=bindings.viewport,
        applicator=bindings.applicator,
        thumbnail_cache=bindings.thumbnail_cache,
        editor_state=bindings.editor_state,
        layout=bindings.layout,
        layout_width=layout_width.resolve,
        scroll_offset=bindings.scroll_offset,
        flush_pending_projection=bindings.flush_pending_projection,
        synchronize_layout=bindings.synchronize_layout,
        publish_render_frame=bindings.publish_render_frame,
        request_update=bindings.request_update,
    )
    selection_layer = PromptProjectionSelectionLayerOwner(
        frame=lambda: bindings.layout.frame,
        selection=bindings.selection,
        viewport_rect=lambda: QRectF(bindings.viewport.rect()),
        scroll_offset=bindings.scroll_offset,
        preview_active=reorder.is_active,
    )
    caret_visual = PromptSurfaceCaretVisualController(
        surface=bindings.surface,
        viewport=bindings.viewport,
        geometry=bindings.caret_geometry,
        is_alive=qt_object_is_alive,
        reorder_preview_active=reorder.is_active,
        surface_is_visible=bindings.surface_is_visible,
        caret_focus_active=bindings.focus.caret_focus_owner_has_focus,
        publish_visual_state=bindings.publish_render_frame,
        selection=bindings.selection,
        caret_suppressed=lambda: bindings.session.exact_weight_edit is not None,
        visible_scroll_bar=bindings.visible_scroll_bar,
        parent=bindings.parent,
    )
    emphasis = PromptProjectionEmphasisOwner(
        session=bindings.session,
        is_projected=bindings.is_projected,
        tokens=bindings.tokens,
        apply_session_paint_state=bindings.apply_session_paint_state,
        apply_accent_paint_state=bindings.apply_accent_paint_state,
        rebuild_projection=bindings.rebuild_projection,
        publish_caret=bindings.publish_caret,
        parent=bindings.parent,
    )
    caret_movement = PromptProjectionCaretMovementController(
        bindings.caret_movement_host,
        state=bindings.caret_state,
        publication=bindings.caret_publication,
        geometry=bindings.caret_geometry,
    )
    return PromptProjectionSurfaceLifecycleRuntime(
        layout_width=layout_width,
        reorder=reorder,
        selection_layer=selection_layer,
        caret_visual=caret_visual,
        emphasis=emphasis,
        caret_movement=caret_movement,
    )


__all__ = [
    "PromptProjectionSurfaceLifecycleBindings",
    "PromptProjectionSurfaceLifecycleRuntime",
    "build_prompt_projection_surface_lifecycle_runtime",
]
