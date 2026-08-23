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

"""Provide semantic and syntax collaborator doubles for interaction tests."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.core.state.semantic_state import (
    PromptEditorSemanticSnapshot,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
)


class SemanticRefreshControllerDouble:
    """Provide no-op semantic refresh scheduling for direct interaction tests."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.queued_sources: list[tuple[str, str]] = []
        self.flush_reasons: list[str] = []
        self.cancel_reasons: list[str] = []

    def queue_source_changed(
        self,
        source_text: str,
        *,
        reason: str,
        prepared_document_view: object | None = None,
        prepared_render_plan: object | None = None,
    ) -> None:
        """Record one queued semantic refresh request."""

        _ = prepared_document_view, prepared_render_plan
        self.queued_sources.append((source_text, reason))

    def flush(self, *, reason: str) -> None:
        """Record one semantic refresh flush request."""

        self.flush_reasons.append(reason)

    def cancel_pending(self, *, reason: str) -> None:
        """Record one semantic refresh cancellation request."""

        self.cancel_reasons.append(reason)


class SyntaxRendererCoordinatorDouble:
    """Record syntax-renderer seam updates requested by the interaction controller."""

    def __init__(self, action_result: object | None = None) -> None:
        """Initialize controller-to-renderer call tracking."""

        self.prompt_state_calls: list[PromptEditorSemanticSnapshot] = []
        self.active_span_calls: list[tuple[PromptSyntaxSpanView | None, int]] = []
        self.refresh_geometry_calls = 0
        self.clear_transient_state_calls = 0
        self.action_result = action_result
        self.syntax_action_calls: list[object] = []

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Record one prompt snapshot replacement."""

        self.prompt_state_calls.append(snapshot)

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Record one caret-active syntax update."""

        self.active_span_calls.append((active_span, cursor_position))

    def refresh_geometry(self) -> None:
        """Record one syntax-renderer geometry refresh request."""

        self.refresh_geometry_calls += 1

    def clear_transient_state(self) -> None:
        """Record one transient-state clear request."""

        self.clear_transient_state_calls += 1

    def syntax_action_at(self, position: object) -> object | None:
        """Return the configured syntax action for one deterministic position."""

        self.syntax_action_calls.append(position)
        return self.action_result


def autocomplete_double() -> SimpleNamespace:
    """Return the minimal autocomplete collaborator used by controller tests."""

    return SimpleNamespace(
        handle_key_press=lambda _event: False,
        refresh_for_query=lambda _query, **_kwargs: None,
        refresh_for_lora_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: None,
        refresh_geometry=lambda: None,
    )


def syntax_renderer_double(
    action_result: object | None = None,
) -> SyntaxRendererCoordinatorDouble:
    """Return a fresh syntax-renderer seam double for controller tests."""

    return SyntaxRendererCoordinatorDouble(action_result=action_result)


def semantic_refresh_controller_double() -> SemanticRefreshControllerDouble:
    """Return a deterministic semantic refresh controller."""

    return SemanticRefreshControllerDouble()


def syntax_service() -> PromptSyntaxService:
    """Return the standard prompt syntax service used by controller tests."""

    return PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
