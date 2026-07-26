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

"""Coordinate syntax-aware prompt renderers inside the presentation layer."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from PySide6.QtCore import QPointF

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.editing.mutation_service import PromptMutation
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

from .async_work import PromptAsyncResultIdentity, PromptSemanticRefreshRequest
from .core.state.editor_state import PromptEditorDocumentState
from .core.state.revisions import (
    PromptSourceIdentity,
)
from .core.state.semantic_state import PromptEditorSemanticSnapshot
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

_LOGGER = get_logger("presentation.editor.prompt_editor.syntax_renderers")


class PromptSyntaxRenderer(Protocol):
    """Describe one syntax-aware renderer plugged into the prompt editor seam."""

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Replace the cached prompt snapshot used for syntax-aware rendering."""

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Refresh the active syntax state for the current caret position."""

    def refresh_geometry(self) -> None:
        """Rebuild cached geometry after the editor viewport moves or resizes."""

    def clear_transient_state(self) -> None:
        """Clear transient hover or gesture state after the editor leaves flow."""

    def hit_test_action(self, position: QPointF) -> PromptSyntaxAction | None:
        """Return the syntax action exposed at one viewport-local position."""


class PromptSyntaxRendererCoordinator:
    """Fan prompt-editor syntax state into an ordered renderer registry."""

    def __init__(self, renderers: Sequence[PromptSyntaxRenderer]) -> None:
        """Store the renderer registry in deterministic paint and hit-test order."""

        self._renderers = list(renderers)

    def add_renderer(self, renderer: PromptSyntaxRenderer) -> None:
        """Register one renderer after composition resolves construction order."""

        self._renderers.append(renderer)

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Push one prompt snapshot and render plan into every registered renderer."""

        for renderer in self._renderers:
            renderer.set_prompt_state(snapshot)

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Push the active syntax state into every registered renderer."""

        for renderer in self._renderers:
            renderer.set_active_span(active_span, cursor_position=cursor_position)

    def refresh_geometry(self) -> None:
        """Request geometry recomputation from every registered renderer."""

        for renderer in self._renderers:
            renderer.refresh_geometry()

    def clear_transient_state(self) -> None:
        """Clear transient hover or gesture state across every renderer."""

        for renderer in self._renderers:
            renderer.clear_transient_state()

    def syntax_action_at(self, position: QPointF) -> PromptSyntaxAction | None:
        """Return the top-most syntax action exposed at one viewport-local point."""

        for renderer in reversed(self._renderers):
            action = renderer.hit_test_action(position)
            if action is not None:
                return action
        return None


class PromptSyntaxStateController:
    """Own current prompt syntax snapshots and renderer publication."""

    def __init__(
        self,
        *,
        active_syntax_span: Callable[[], PromptSyntaxSpanView | None],
        cursor_position: Callable[[], int],
        editor_session_id: int,
        renderers: PromptSyntaxRendererCoordinator,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        state: PromptEditorDocumentState[
            PromptDocumentView,
            PromptSyntaxRenderPlan,
            PromptProjectionDocument,
        ],
        source_text: Callable[[], str],
        source_changed_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Build the initial prompt snapshot and store publication collaborators."""

        self._active_syntax_span_provider = active_syntax_span
        self._cursor_position = cursor_position
        self._editor_session_id = editor_session_id
        self._renderers = renderers
        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._state = state
        self._source_text = source_text
        self._source_changed_callback = source_changed_callback
        self._pending_document_view: PromptDocumentView | None = None
        initial_document_view = self._document_service.build_document_view(
            self._source_text()
        )
        self._active_syntax_span: PromptSyntaxSpanView | None = None
        self.replace_prompt_state(initial_document_view)
        self.refresh_active_span()

    @property
    def document_view(self) -> PromptDocumentView:
        """Return the current application-owned prompt document view."""

        return self._state.semantic.document

    @property
    def render_plan(self) -> PromptSyntaxRenderPlan:
        """Return the current syntax render plan."""

        return self._state.semantic.render_plan

    @property
    def semantic_snapshot(self) -> PromptEditorSemanticSnapshot:
        """Return the atomic semantic snapshot published to renderers."""

        return self._state.semantic

    @property
    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the current cursor-derived syntax span."""

        return self._active_syntax_span

    @property
    def pending_document_view(self) -> PromptDocumentView | None:
        """Return a prepared document view waiting for semantic publication."""

        return self._pending_document_view

    def clear_pending_document_view(self) -> None:
        """Forget any prepared semantic snapshot after explicit state adoption."""

        self._pending_document_view = None

    def refresh_geometry(self) -> None:
        """Request geometry recomputation from syntax renderers."""

        self._renderers.refresh_geometry()

    def clear_transient_state(self) -> None:
        """Clear transient syntax renderer state."""

        self._renderers.clear_transient_state()

    def add_renderer(self, renderer: PromptSyntaxRenderer) -> None:
        """Register and initialize one renderer with the current syntax state."""

        self._renderers.add_renderer(renderer)
        renderer.set_prompt_state(self._state.semantic)
        renderer.set_active_span(
            self._active_syntax_span,
            cursor_position=self._cursor_position(),
        )

    def syntax_action_at(self, position: QPointF) -> PromptSyntaxAction | None:
        """Return the top-most syntax action exposed at one viewport-local point."""

        return self._renderers.syntax_action_at(position)

    def current_semantic_source_text(self) -> str:
        """Return current editor source text for semantic refresh freshness."""

        return self._source_text()

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the cached semantic snapshot."""

        return self._state.semantic.document.source_text

    def current_semantic_is_current(self) -> bool:
        """Return whether semantic identity matches the live source identity."""

        return self._state.semantic.identity.source is self._state.source_identity

    def rebase_current_semantic_source_identity(self) -> bool:
        """Republish exact same-text semantics under the live source identity."""

        semantic = self._state.semantic
        if semantic.document.source_text != self._source_text():
            return False
        if semantic.identity.source is self._state.source_identity:
            return True
        if not self.replace_prompt_state_with_render_plan(
            semantic.document,
            semantic.render_plan,
        ):
            return False
        self._state.rebase_equivalent_downstream(self._state.semantic)
        return True

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current source identity for semantic stale-result checks."""

        source_identity = self._state.source_identity
        if source_identity is not None and source_identity.source_length is None:
            source_identity = PromptSourceIdentity(
                source_revision=source_identity.source_revision,
                source_length=len(self._source_text()),
            )
        return PromptAsyncResultIdentity(
            request_id=request_id,
            editor_session_id=self._editor_session_id,
            source_identity=source_identity,
            feature_profile_id=tuple(self._syntax_profile.enabled_syntaxes),
            scene_context_id=None,
            cube_context_id=None,
        )

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Adopt a semantic refresh request already proved fresh by async owner."""

        pending_document_view = request.prepared_document_view
        pending_render_plan = request.prepared_render_plan
        if (
            pending_document_view is not None
            and pending_document_view.source_text == request.source_text
            and pending_render_plan is not None
        ):
            self._pending_document_view = None
            self.replace_prompt_state_with_render_plan(
                pending_document_view,
                pending_render_plan,
            )
        elif (
            pending_document_view is not None
            and pending_document_view.source_text == request.source_text
        ):
            self._pending_document_view = None
            self.replace_prompt_state(pending_document_view)
        else:
            document_view = self._document_service.build_document_view(
                request.source_text
            )
            self.replace_prompt_state(document_view)
        self.refresh_active_span()

    def apply_mutation(
        self,
        mutation: PromptMutation,
        *,
        current_text: str,
        render_plan: PromptSyntaxRenderPlan | None = None,
    ) -> bool:
        """Adopt prompt state from a source-applied command result."""

        if mutation.text != current_text:
            _LOGGER.warning(
                "Prompt mutation source change reached legacy state-adoption path"
                " | mutation_source_length=%s current_source_length=%s",
                len(mutation.text),
                len(current_text),
            )
            return False

        self._pending_document_view = None
        if render_plan is None:
            applied = self.replace_prompt_state(mutation.document_view)
        else:
            applied = self.replace_prompt_state_with_render_plan(
                mutation.document_view,
                render_plan,
            )
        if applied:
            self.refresh_active_span()
        return applied

    def replace_prompt_state(self, document_view: PromptDocumentView) -> bool:
        """Replace the cached prompt snapshot and build a syntax render plan."""

        try:
            syntax_render_plan = self._syntax_service.build_render_plan(
                document_view,
                self._syntax_profile,
            )
        except Exception as error:
            log_warning_exception(
                _LOGGER,
                "Prompt syntax render-plan refresh failed",
                error=error,
                source_length=len(document_view.source_text),
                previous_source_length=len(self._state.semantic.document.source_text),
            )
            return False
        return self.replace_prompt_state_with_render_plan(
            document_view,
            syntax_render_plan,
        )

    def replace_prompt_state_with_render_plan(
        self,
        document_view: PromptDocumentView,
        syntax_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Replace cached prompt state using an already prepared render plan."""

        if document_view.source_text != self._source_text():
            _LOGGER.warning(
                "Prompt semantic publication rejected mismatched source"
                " | prepared_source_length=%s live_source_length=%s",
                len(document_view.source_text),
                len(self._source_text()),
            )
            return False
        previous_snapshot = self._state.semantic
        candidate = self._state.prepare_semantic(
            document_view,
            syntax_render_plan,
            source_identity=self._state.source_identity,
        )
        try:
            self._renderers.set_prompt_state(candidate)
        except Exception as error:
            self._state.restore_semantic(previous_snapshot)
            log_warning_exception(
                _LOGGER,
                "Prompt syntax render-plan refresh failed",
                error=error,
                source_length=len(document_view.source_text),
                previous_source_length=len(previous_snapshot.document.source_text),
            )
            return False
        self._state.adopt_semantic(candidate)
        if (
            document_view.source_text != previous_snapshot.document.source_text
            and self._source_changed_callback is not None
        ):
            self._source_changed_callback("source_text_changed")
        return True

    def refresh_active_span(self) -> None:
        """Publish the cursor-derived active syntax span to renderers."""

        cursor_position = self._cursor_position()
        editor_active_span = self._active_syntax_span_provider()
        self._active_syntax_span = editor_active_span or self._syntax_span_at_position(
            cursor_position
        )
        self._renderers.set_active_span(
            self._active_syntax_span,
            cursor_position=cursor_position,
        )

    def _syntax_span_at_position(
        self,
        position: int,
    ) -> PromptSyntaxSpanView | None:
        """Return the innermost syntax span matching one cursor position."""

        for span in reversed(self._state.semantic.render_plan.syntax_spans):
            if span.start < position < span.end:
                return span
        return None


__all__ = [
    "PromptSyntaxRenderer",
    "PromptSyntaxRendererCoordinator",
    "PromptSyntaxStateController",
    "PromptEditorSemanticSnapshot",
]
