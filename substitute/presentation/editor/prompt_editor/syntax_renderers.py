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
from typing import Protocol, cast

from PySide6.QtCore import QPointF

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptMutation,
    PromptSyntaxAction,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
    PromptSyntaxSpanView,
)
from substitute.shared.logging.logger import get_logger, log_warning_exception

from .async_work import PromptAsyncResultIdentity, PromptSemanticRefreshRequest
from .commands import PromptCommandSourceIdentity

_LOGGER = get_logger("presentation.editor.prompt_editor.syntax_renderers")


class PromptSyntaxRenderer(Protocol):
    """Describe one syntax-aware renderer plugged into the prompt editor seam."""

    def set_prompt_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
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
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Push one prompt snapshot and render plan into every registered renderer."""

        for renderer in self._renderers:
            renderer.set_prompt_state(document_view, render_plan)

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


class _PromptSyntaxStateCursor(Protocol):
    """Describe the cursor API needed for active syntax ownership."""

    def position(self) -> int:
        """Return the current source cursor position."""


class PromptSyntaxStateEditor(Protocol):
    """Describe editor state needed to publish prompt syntax snapshots."""

    def toPlainText(self) -> str:
        """Return the editor's current source text."""

    def textCursor(self) -> _PromptSyntaxStateCursor:
        """Return the editor cursor used for active syntax lookup."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity for stale-result checks."""

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the editor-owned active syntax span when available."""


class PromptSyntaxStateController:
    """Own current prompt syntax snapshots and renderer publication."""

    def __init__(
        self,
        *,
        editor: PromptSyntaxStateEditor,
        renderers: PromptSyntaxRendererCoordinator,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        source_changed_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Build the initial prompt snapshot and store publication collaborators."""

        self._editor = editor
        self._renderers = renderers
        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._source_changed_callback = source_changed_callback
        self._pending_document_view: PromptDocumentView | None = None
        self._document_view = self._document_service.build_document_view(
            self._editor.toPlainText()
        )
        self._render_plan = PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        )
        self._active_syntax_span: PromptSyntaxSpanView | None = None
        self.replace_prompt_state(self._document_view)
        self.refresh_active_span()

    @property
    def document_view(self) -> PromptDocumentView:
        """Return the current application-owned prompt document view."""

        return self._document_view

    @property
    def render_plan(self) -> PromptSyntaxRenderPlan:
        """Return the current syntax render plan."""

        return self._render_plan

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
        renderer.set_prompt_state(self._document_view, self._render_plan)
        renderer.set_active_span(
            self._active_syntax_span,
            cursor_position=self._editor.textCursor().position(),
        )

    def syntax_action_at(self, position: QPointF) -> PromptSyntaxAction | None:
        """Return the top-most syntax action exposed at one viewport-local point."""

        return self._renderers.syntax_action_at(position)

    def current_semantic_source_text(self) -> str:
        """Return current editor source text for semantic refresh freshness."""

        return self._editor.toPlainText()

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the cached semantic snapshot."""

        return self._document_view.source_text

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current source identity for semantic stale-result checks."""

        source_identity = self._editor.prompt_command_source_identity()
        source_revision = (
            None if source_identity is None else source_identity.source_revision
        )
        source_length = (
            len(self._editor.toPlainText())
            if source_identity is None or source_identity.source_length is None
            else source_identity.source_length
        )
        return PromptAsyncResultIdentity(
            request_id=request_id,
            editor_session_id=id(self._editor),
            source_revision=source_revision,
            source_length=source_length,
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
                previous_source_length=len(self._document_view.source_text),
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

        previous_document_view = self._document_view
        previous_render_plan = self._render_plan
        try:
            self._document_view = document_view
            self._render_plan = syntax_render_plan
            self._renderers.set_prompt_state(document_view, syntax_render_plan)
        except Exception as error:
            self._document_view = previous_document_view
            self._render_plan = previous_render_plan
            log_warning_exception(
                _LOGGER,
                "Prompt syntax render-plan refresh failed",
                error=error,
                source_length=len(document_view.source_text),
                previous_source_length=len(previous_document_view.source_text),
            )
            return False
        if (
            document_view.source_text != previous_document_view.source_text
            and self._source_changed_callback is not None
        ):
            self._source_changed_callback("source_text_changed")
        return True

    def refresh_active_span(self) -> None:
        """Publish the cursor-derived active syntax span to renderers."""

        cursor_position = self._editor.textCursor().position()
        editor_active_span = self._editor_active_syntax_span()
        self._active_syntax_span = editor_active_span or self._syntax_span_at_position(
            cursor_position
        )
        self._renderers.set_active_span(
            self._active_syntax_span,
            cursor_position=cursor_position,
        )

    def _editor_active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the editor-owned active syntax span when the host exposes it."""

        active_span_getter = getattr(self._editor, "active_syntax_span", None)
        if active_span_getter is None:
            return None
        return cast(PromptSyntaxSpanView | None, active_span_getter())

    def _syntax_span_at_position(
        self,
        position: int,
    ) -> PromptSyntaxSpanView | None:
        """Return the innermost syntax span matching one cursor position."""

        for span in reversed(self._render_plan.syntax_spans):
            if span.start < position < span.end:
                return span
        return None


__all__ = [
    "PromptSyntaxRenderer",
    "PromptSyntaxRendererCoordinator",
    "PromptSyntaxStateController",
    "PromptSyntaxStateEditor",
]
