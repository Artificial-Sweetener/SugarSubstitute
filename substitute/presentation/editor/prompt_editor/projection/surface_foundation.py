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

"""Build source-independent foundations for the prompt projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)

from ..core.editing.session import PromptEditingSession
from ..core.projection.document import PromptProjectionDisplayMode
from ..core.projection.tokens import PromptProjectionToken
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .applicator import PromptProjectionApplicator
from .builder import PromptProjectionBuilder
from .caret_state_owner import PromptProjectionCaretStateOwner
from .content_media_owner import PromptProjectionContentMediaOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .emphasis_renderer import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
)
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionFrameStatePublisher,
    build_initial_prompt_projection_state,
)
from .inline_renderer_registry import PromptProjectionInlineObjectRendererRegistry
from .lora_renderer import PromptLoraInlineObjectRenderer
from .lora_surface_features import (
    PromptSurfaceLoraFeatureDelegate,
    PromptSurfaceLoraFeatureHost,
    PromptSurfaceLoraThumbnailPreloader,
)
from .search_highlight_owner import PromptSearchHighlightLayerOwner
from .session import PromptProjectionSession
from .source_line_chrome import PromptSourceLineChrome
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .undo_payload import PromptProjectionUndoPayload
from .wildcard_renderer import PromptWildcardInlineObjectRenderer


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceFoundationBindings:
    """Declare external inputs required to build projection foundations."""

    host: PromptSurfaceLoraFeatureHost
    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    document_semantics: PromptDocumentSemantics | None
    lora_thumbnail_cache: PromptLoraThumbnailCache | None
    lora_thumbnail_preloader: PromptSurfaceLoraThumbnailPreloader | None
    publish_thumbnail_media: Callable[[str], None]
    publish_context_menu: Callable[[PromptProjectionToken, QPoint], None]


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceFoundation:
    """Expose the source-independent owners shared by surface runtimes."""

    applicator: PromptProjectionApplicator
    thumbnail_cache: PromptLoraThumbnailCache
    session: PromptProjectionSession
    layout: PromptLayoutEditToFrameCoordinator
    content_media: PromptProjectionContentMediaOwner
    lora_features: PromptSurfaceLoraFeatureDelegate
    editor_state: PromptProjectionEditorState
    frame_state: PromptProjectionFrameStatePublisher
    source_line_chrome: PromptSourceLineChrome
    search_highlight: PromptSearchHighlightLayerOwner
    caret_state: PromptProjectionCaretStateOwner
    transient_overlays: PromptProjectionTransientEditOverlayController


def build_prompt_projection_surface_foundation(
    bindings: PromptProjectionSurfaceFoundationBindings,
) -> PromptProjectionSurfaceFoundation:
    """Build stable projection state before lifecycle-dependent collaborators."""

    applicator = PromptProjectionApplicator(
        PromptProjectionBuilder(document_semantics=bindings.document_semantics)
    )
    thumbnail_cache = bindings.lora_thumbnail_cache or PromptLoraThumbnailCache()
    session = PromptProjectionSession()
    layout = PromptLayoutEditToFrameCoordinator(
        PromptProjectionInlineObjectRendererRegistry(
            (
                PromptEmphasisPrefixRenderer(),
                PromptEmphasisSuffixRenderer(),
                PromptLoraInlineObjectRenderer(thumbnail_cache),
                PromptWildcardInlineObjectRenderer(),
            )
        )
    )
    content_media = PromptProjectionContentMediaOwner()
    editor_state = build_initial_prompt_projection_state(
        source=bindings.editing_session.source_snapshot(),
        applicator=applicator,
        document_semantics=bindings.document_semantics,
        display_mode=PromptProjectionDisplayMode.PROJECTED,
        session=session,
        scene_error_keys=frozenset(),
    )
    frame_state = PromptProjectionFrameStatePublisher(editor_state)
    source_line_chrome = PromptSourceLineChrome()
    search_highlight = PromptSearchHighlightLayerOwner()
    initial_caret_state = (
        editor_state.projection.document.caret_map.state_for_source_position(0)
    )
    caret_state = PromptProjectionCaretStateOwner(initial_caret_state)
    transient_overlays = PromptProjectionTransientEditOverlayController()
    lora_features = PromptSurfaceLoraFeatureDelegate(
        bindings.host,
        thumbnail_cache=thumbnail_cache,
        thumbnail_preloader=bindings.lora_thumbnail_preloader,
        publish_thumbnail_media=bindings.publish_thumbnail_media,
        publish_context_menu=bindings.publish_context_menu,
    )
    update_lora_thumbnail = lora_features.update_lora_thumbnail_pixmap
    thumbnail_cache.pixmap_ready.connect(
        lambda key: update_lora_thumbnail(layout.frame.geometry, key)
    )
    return PromptProjectionSurfaceFoundation(
        applicator=applicator,
        thumbnail_cache=thumbnail_cache,
        session=session,
        layout=layout,
        content_media=content_media,
        lora_features=lora_features,
        editor_state=editor_state,
        frame_state=frame_state,
        source_line_chrome=source_line_chrome,
        search_highlight=search_highlight,
        caret_state=caret_state,
        transient_overlays=transient_overlays,
    )


__all__ = [
    "PromptProjectionSurfaceFoundation",
    "PromptProjectionSurfaceFoundationBindings",
    "build_prompt_projection_surface_foundation",
]
