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

"""Tests for the prompt editor host command adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptMutationService,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptTriggerWordInsertionRequest,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptEditorCommandAdapter,
)


@dataclass(slots=True)
class _Cursor:
    """Provide source-backed cursor reads for adapter insertion tests."""

    selection_start: int
    selection_end: int
    cursor_position: int

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether this fake cursor has a selected range."""

        return self.selection_start != self.selection_end

    def selectionStart(self) -> int:  # noqa: N802
        """Return the fake selection start endpoint."""

        return self.selection_start

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the fake selection end endpoint."""

        return self.selection_end

    def position(self) -> int:
        """Return the fake cursor position."""

        return self.cursor_position


@dataclass(frozen=True, slots=True)
class _InsertState:
    """Carry one fake context-menu insertion target."""

    insert_position: int | None
    should_replace_selection: bool | None


class _Executor:
    """Capture command adapter calls made to the current executor port."""

    def __init__(self) -> None:
        """Prepare fake command results and observations."""

        self.source_identity = PromptCommandSourceIdentity(
            source_revision=7,
            source_length=12,
        )
        self.autocomplete_result: PromptCommandResult[object] = (
            PromptCommandResult.completed("autocomplete")
        )
        self.diagnostic_result: PromptDiagnosticCommandResult[object] = (
            PromptDiagnosticCommandResult(command_name="diagnostic", status="completed")
        )
        self.weight_result: PromptWeightCommandResult[object] = (
            PromptWeightCommandResult(command_name="weight", status="completed")
        )
        self.reorder_result: PromptReorderCommandResult[object] = (
            PromptReorderCommandResult(command_name="reorder", status="completed")
        )
        self.replacement_result: PromptCommandResult[object] = (
            PromptCommandResult.completed("replacement")
        )
        self.calls: list[tuple[str, object]] = []
        self.source_replacements: list[PromptCommandTextReplacement] = []
        self.source_replacement_command_names: list[str] = []
        self.full_text_calls: list[tuple[str, str, bool | None]] = []
        self.weight_services: list[
            tuple[PromptMutationService, PromptSyntaxService, PromptSyntaxProfile]
        ] = []
        self.reorder_services: list[
            tuple[PromptMutationService, PromptSyntaxService, PromptSyntaxProfile]
        ] = []

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the fake source identity."""

        self.calls.append(("source_identity", self.source_identity))
        return self.source_identity

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[Any]:
        """Record one autocomplete acceptance."""

        self.calls.append(("autocomplete", acceptance))
        return self.autocomplete_result

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[Any]:
        """Record one diagnostic action."""

        self.calls.append(("diagnostic", action))
        return self.diagnostic_result

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[Any]:
        """Record one weight action and its services."""

        self.calls.append(("weight", request))
        self.weight_services.append((mutation_service, syntax_service, syntax_profile))
        return self.weight_result

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[Any]:
        """Record one reorder action and its services."""

        self.calls.append(("reorder", request))
        self.reorder_services.append((mutation_service, syntax_service, syntax_profile))
        return self.reorder_result

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[Any]:
        """Record one source replacement."""

        self.calls.append(("source_replacement", replacement))
        self.source_replacements.append(replacement)
        self.source_replacement_command_names.append(command_name)
        return self.replacement_result

    def execute_trigger_word_insertion(
        self,
        request: PromptTriggerWordInsertionRequest,
    ) -> PromptCommandResult[Any]:
        """Record one typed trigger-word insertion request."""

        self.calls.append(("trigger_words", request))
        return self.replacement_result

    def set_plain_text(self, text: str) -> None:
        """Record one plain text replacement."""

        self.full_text_calls.append(("set_plain_text", text, None))

    def set_source_text(self, text: str) -> None:
        """Record one exact source replacement."""

        self.full_text_calls.append(("set_source_text", text, None))

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Record one baseline replacement."""

        self.full_text_calls.append(("replace_baseline_text", text, exact_source))

    def replace_document_text(self, text: str) -> None:
        """Record one document replacement."""

        self.full_text_calls.append(("replace_document_text", text, None))

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Record one document replacement with prepared prompt state."""

        _ = document_view
        _ = render_plan
        self.full_text_calls.append(
            ("replace_document_text_with_prompt_state", text, None)
        )


class _AdapterHarness:
    """Own adapter test fakes and their mutable observations."""

    def __init__(
        self,
        *,
        cursor: _Cursor | None = None,
        insert_state: _InsertState | None = None,
    ) -> None:
        """Create one command adapter with fake collaborators."""

        self.executor = _Executor()
        self.cursor = cursor or _Cursor(0, 0, 0)
        self.insert_state = insert_state or _InsertState(
            insert_position=None,
            should_replace_selection=None,
        )
        self.focus_count = 0
        self.adapter = PromptEditorCommandAdapter(
            executor=self.executor,
            cursor_provider=lambda: self.cursor,
            context_insert_state_provider=lambda: self.insert_state,
            focus_restorer=self._restore_focus,
        )

    def _restore_focus(self) -> None:
        """Record one focus restoration."""

        self.focus_count += 1


def test_adapter_delegates_public_command_methods_to_executor() -> None:
    """Public command methods should delegate through the adapter boundary."""

    harness = _AdapterHarness()
    acceptance = cast(PromptAutocompleteAcceptance, object())
    diagnostic_action = cast(PromptDiagnosticAction, object())
    weight_request = cast(PromptWeightActionRequest, object())
    reorder_request = cast(PromptReorderLayoutCommitRequest, object())
    mutation_service = cast(PromptMutationService, object())
    syntax_service = cast(PromptSyntaxService, object())
    syntax_profile = cast(PromptSyntaxProfile, object())
    replacement = PromptCommandTextReplacement(
        source_range=PromptCommandSourceRange(start=1, end=2),
        replacement_text="x",
        origin=PromptSourceEditOrigin.PROGRAMMATIC,
    )

    assert (
        harness.adapter.prompt_command_source_identity()
        is harness.executor.source_identity
    )
    assert (
        harness.adapter.execute_autocomplete_acceptance(acceptance)
        is harness.executor.autocomplete_result
    )
    assert (
        harness.adapter.execute_diagnostic_action(diagnostic_action)
        is harness.executor.diagnostic_result
    )
    assert (
        harness.adapter.execute_weight_action(
            weight_request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        is harness.executor.weight_result
    )
    assert (
        harness.adapter.execute_reorder_action(
            reorder_request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        is harness.executor.reorder_result
    )
    assert (
        harness.adapter.execute_source_replacement(
            replacement,
            command_name="replace",
        )
        is harness.executor.replacement_result
    )

    assert harness.executor.calls == [
        ("source_identity", harness.executor.source_identity),
        ("autocomplete", acceptance),
        ("diagnostic", diagnostic_action),
        ("weight", weight_request),
        ("reorder", reorder_request),
        ("source_replacement", replacement),
    ]
    assert harness.executor.weight_services == [
        (mutation_service, syntax_service, syntax_profile)
    ]
    assert harness.executor.reorder_services == [
        (mutation_service, syntax_service, syntax_profile)
    ]


def test_context_menu_insert_replaces_live_selection_when_allowed() -> None:
    """Context insertion should replace selected source text by default."""

    harness = _AdapterHarness(
        cursor=_Cursor(3, 8, 8),
        insert_state=_InsertState(insert_position=1, should_replace_selection=None),
    )

    result = harness.adapter.insert_context_menu_text("delta")

    assert result is harness.executor.replacement_result
    assert harness.focus_count == 1
    assert harness.executor.source_replacement_command_names == [
        "context_menu_insert_text"
    ]
    replacement = harness.executor.source_replacements[0]
    assert replacement.source_range == PromptCommandSourceRange(start=3, end=8)
    assert replacement.replacement_text == "delta"
    assert replacement.origin is PromptSourceEditOrigin.PROGRAMMATIC
    assert replacement.exact_source is False
    assert replacement.record_undo is True


def test_context_menu_insert_uses_menu_position_when_selection_replacement_blocked() -> (
    None
):
    """Context insertion should use the stored menu target when selection is stale."""

    harness = _AdapterHarness(
        cursor=_Cursor(3, 8, 8),
        insert_state=_InsertState(insert_position=11, should_replace_selection=False),
    )

    harness.adapter.insert_context_menu_text("delta", command_name="custom_insert")

    replacement = harness.executor.source_replacements[0]
    assert replacement.source_range == PromptCommandSourceRange(start=11, end=11)
    assert harness.executor.source_replacement_command_names == ["custom_insert"]
    assert harness.focus_count == 1


def test_context_menu_insert_falls_back_to_cursor_position() -> None:
    """Context insertion should fall back to the live cursor position."""

    harness = _AdapterHarness(
        cursor=_Cursor(5, 5, 9),
        insert_state=_InsertState(insert_position=None, should_replace_selection=None),
    )

    harness.adapter.insert_context_menu_text("delta")

    replacement = harness.executor.source_replacements[0]
    assert replacement.source_range == PromptCommandSourceRange(start=9, end=9)
    assert harness.focus_count == 1
