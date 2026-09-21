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

"""Publish source revisions and invalidate every source-derived view."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from .freshness_controller import PromptProjectionFreshnessController
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController

PromptSourceChangeEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptSourceChangePublicationOwner:
    """Own the ordered publication effects of one committed source revision."""

    def __init__(
        self,
        *,
        editor_state: PromptSourceChangeEditorState,
        freshness: PromptProjectionFreshnessController,
        overlays: PromptProjectionTransientEditOverlayController,
        input_method_source_changed: Callable[[], None],
        clear_reorder_for_source_change: Callable[[], None],
        invalidate_render_for_source_change: Callable[[bool], None],
    ) -> None:
        """Store authoritative state and the three presentation invalidations."""

        self._editor_state = editor_state
        self._freshness = freshness
        self._overlays = overlays
        self._input_method_source_changed = input_method_source_changed
        self._clear_reorder_for_source_change = clear_reorder_for_source_change
        self._invalidate_render_for_source_change = invalidate_render_for_source_change

    def publish(
        self,
        *,
        deferrable_projection: bool,
        source_snapshot: PromptSourceSnapshot,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> PromptSourceIdentity:
        """Publish one source revision with all dependent invalidation effects."""

        self._input_method_source_changed()
        if not deferrable_projection:
            self._overlays.clear()
        source_identity = self._editor_state.publish_source(source_snapshot)
        self._clear_reorder_for_source_change()
        self._invalidate_render_for_source_change(clear_diagnostic_fragment_cache)
        self._freshness.mark_source_text_changed(
            deferrable_projection=deferrable_projection,
            source_revision=source_identity.source_revision,
        )
        return source_identity


__all__ = ["PromptSourceChangePublicationOwner"]
