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

"""Tests for LoRA metadata refresh projection ownership."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptDocumentService,
    PromptMutationService,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
    PromptSyntaxSpanView,
)
from substitute.presentation.editor.prompt_editor.syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


class _CursorDouble:
    """Expose the cursor position consumed by syntax-state refreshes."""

    def __init__(self, *, position: int) -> None:
        """Store the cursor position."""

        self._position = position

    def position(self) -> int:
        """Return the configured cursor position."""

        return self._position


class _EditorDouble:
    """Provide the editor surface required by LoRA projection refresh."""

    def __init__(self, *, text: str, cursor_position: int) -> None:
        """Store prompt text and cursor state."""

        self._text = text
        self._cursor = _CursorDouble(position=cursor_position)
        self.replace_document_text_calls: list[str] = []

    def textCursor(self) -> _CursorDouble:  # noqa: N802
        """Return the configured text cursor."""

        return self._cursor

    def toPlainText(self) -> str:  # noqa: N802
        """Return the configured prompt text."""

        return self._text

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for direct projection-refresh tests."""

        return None

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return no editor-owned active syntax span."""

        return None

    def replace_document_text(self, text: str) -> None:
        """Record unexpected source edits."""

        self.replace_document_text_calls.append(text)
        self._text = text


class _SemanticRefreshDouble:
    """Provide no-op semantic refresh scheduling for interaction construction."""

    def queue_source_changed(
        self,
        source_text: str,
        *,
        reason: str,
        prepared_document_view: object | None = None,
        prepared_render_plan: object | None = None,
    ) -> None:
        """Fail if the projection refresh attempts to queue semantic work."""

        _ = source_text, reason, prepared_document_view, prepared_render_plan
        raise AssertionError("LoRA projection refresh should not queue semantics.")

    def flush(self, *, reason: str) -> None:
        """Fail if the projection refresh attempts to flush semantics."""

        _ = reason
        raise AssertionError("LoRA projection refresh should not flush semantics.")

    def cancel_pending(self, *, reason: str) -> None:
        """Fail if the projection refresh attempts to cancel semantics."""

        _ = reason
        raise AssertionError("LoRA projection refresh should not cancel semantics.")


class _SyntaxRendererCoordinatorDouble:
    """Record syntax-renderer state publication."""

    def __init__(self) -> None:
        """Initialize renderer publication tracking."""

        self.prompt_state_calls: list[
            tuple[PromptDocumentView, PromptSyntaxRenderPlan]
        ] = []
        self.active_span_calls: list[tuple[PromptSyntaxSpanView | None, int]] = []
        self.refresh_geometry_calls = 0
        self.clear_transient_state_calls = 0

    def set_prompt_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Record one prompt-state publication."""

        self.prompt_state_calls.append((document_view, render_plan))

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Record one active-span publication."""

        self.active_span_calls.append((active_span, cursor_position))

    def refresh_geometry(self) -> None:
        """Record geometry refresh requests."""

        self.refresh_geometry_calls += 1

    def clear_transient_state(self) -> None:
        """Record transient state clears."""

        self.clear_transient_state_calls += 1

    def syntax_action_at(self, position: object) -> None:
        """Return no syntax action for projection-refresh tests."""

        _ = position
        return None


class _OverlayFactoryDouble:
    """Fail fast if LoRA projection refresh tries to create reorder overlays."""

    def create_overlay(self, editor: object, layout_policy: object) -> object:
        """Fail because LoRA projection refresh must not enter reorder mode."""

        _ = editor, layout_policy
        raise AssertionError("LoRA projection refresh should not create overlays.")


def test_refresh_lora_render_metadata_republishes_lora_projection_state() -> None:
    """LoRA metadata refresh rebuilds render state without editing source."""

    controller, editor, renderers = _lora_projection_controller(
        text="<lora:midna:1>",
        cursor_position=14,
    )
    renderers.prompt_state_calls.clear()

    refreshed = controller.refresh_lora_render_metadata(reason="lora_metadata")

    assert refreshed is True
    assert editor.replace_document_text_calls == []
    assert renderers.prompt_state_calls
    document_view, render_plan = renderers.prompt_state_calls[-1]
    assert document_view is controller.document_view
    assert render_plan.renderer_view_for_kind("lora") is not None


def test_refresh_lora_render_metadata_ignores_prompts_without_lora_spans() -> None:
    """LoRA metadata refresh skips projection work when no LoRA syntax is present."""

    controller, editor, renderers = _lora_projection_controller(
        text="1girl",
        cursor_position=5,
    )
    renderers.prompt_state_calls.clear()

    refreshed = controller.refresh_lora_render_metadata(reason="lora_metadata")

    assert refreshed is False
    assert editor.replace_document_text_calls == []
    assert renderers.prompt_state_calls == []


def _lora_projection_controller(
    *,
    text: str,
    cursor_position: int,
) -> tuple[Any, _EditorDouble, _SyntaxRendererCoordinatorDouble]:
    """Build a prompt interaction controller for LoRA projection refresh tests."""

    interaction_module = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.controller"
    )
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(EmptyPromptWildcardCatalogGateway())
    syntax_profile = prompt_syntax_profile("lora")
    editor = _EditorDouble(text=text, cursor_position=cursor_position)
    renderers = _SyntaxRendererCoordinatorDouble()
    syntax_state = PromptSyntaxStateController(
        editor=editor,
        renderers=cast(PromptSyntaxRendererCoordinator, renderers),
        document_service=document_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
    )
    controller = interaction_module.PromptInteractionController(
        editor,
        autocomplete=_autocomplete_double(),
        syntax_state=syntax_state,
        document_service=document_service,
        mutation_service=PromptMutationService(),
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        semantic_refresh_controller=_SemanticRefreshDouble(),
        reorder_overlay_factory=_OverlayFactoryDouble(),
    )
    return controller, editor, renderers


def _autocomplete_double() -> SimpleNamespace:
    """Return the minimal autocomplete collaborator used by interaction tests."""

    return SimpleNamespace(
        handle_key_press=lambda _event: False,
        refresh_for_query=lambda _query, **_kwargs: None,
        refresh_for_lora_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: None,
        refresh_geometry=lambda: None,
    )
