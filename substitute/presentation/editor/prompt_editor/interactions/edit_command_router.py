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

"""Route prompt feature mutation commands through the edit-controller boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptMutationService,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.prompt_structured_text_mutation_service import (
    PromptStructuredTextMutationService,
)

from ..commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptPasteImportCommandResult,
    PromptPreparedDanbooruImportRequest,
    PromptEditorCommand,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptReplaceFullSourceCommand,
    PromptReplaceSourceRangeCommand,
    PromptTriggerWordInsertionRequest,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    build_autocomplete_acceptance_command,
    build_diagnostic_action_command,
    build_prepared_danbooru_import_command,
    build_reorder_layout_commit_command,
    build_trigger_word_insertion_command,
    build_weight_action_command,
)
from ..editing_session import (
    PromptEditingSessionSourceChange,
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
    PromptUndoAvailabilityChange,
    PromptUndoSnapshot,
)
from ..editing_session.edit_controller import (
    PromptEditController,
    PromptEditControllerResult,
    PromptMutationSignalIntent,
    PromptOptimisticPromptState,
    PromptProjectionMutationSink,
    PromptProjectionSourceApplicationMode,
    PromptProjectionSourceChangeApplication,
)

TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class _RouterSourceState:
    """Carry source state read from the live editor before dispatch."""

    text: str
    cursor_position: int
    anchor_position: int
    exact_source: bool


class PromptEditCommandRouter(Generic[TPayload]):
    """Own feature command construction and route committed edits to projection."""

    def __init__(
        self,
        *,
        edit_controller: PromptEditController[TPayload],
        normalizer: PromptSourceNormalizer,
        mutation_sink: PromptProjectionMutationSink[TPayload],
        source_text_provider: Callable[[], str],
        cursor_position_provider: Callable[[], int],
        anchor_position_provider: Callable[[], int],
        exact_source_provider: Callable[[], bool],
        structured_text_mutations: PromptStructuredTextMutationService | None = None,
    ) -> None:
        """Bind command construction to editing-session and projection boundaries."""

        self._edit_controller = edit_controller
        self._normalizer = normalizer
        self._mutation_sink = mutation_sink
        self._source_text_provider = source_text_provider
        self._cursor_position_provider = cursor_position_provider
        self._anchor_position_provider = anchor_position_provider
        self._exact_source_provider = exact_source_provider
        self._structured_text_mutations = structured_text_mutations

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current source identity for prepared commands."""

        return self._edit_controller.prompt_command_source_identity()

    def current_undo_snapshot(self) -> PromptUndoSnapshot[TPayload]:
        """Return the controller-owned undo snapshot for feature collaborators."""

        return self._edit_controller.current_undo_snapshot()

    def set_plain_text(self, text: str) -> None:
        """Replace the full raw prompt source text with normalized semantics."""

        self._replace_full_source_text(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=False,
            record_undo=True,
            clear_history=False,
            trace_name="set_plain_text",
            reset_scroll_to_top=True,
        )

    def set_source_text(self, text: str) -> None:
        """Replace the full raw prompt source text exactly."""

        self._replace_full_source_text(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=True,
            record_undo=True,
            clear_history=False,
            trace_name="set_source_text",
            reset_scroll_to_top=True,
        )

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Replace loaded/restored prompt text and make it the undo baseline."""

        self._replace_full_source_text(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=exact_source,
            record_undo=False,
            clear_history=True,
            trace_name="replace_baseline_text",
            reset_scroll_to_top=True,
        )

    def replace_document_text(self, text: str) -> None:
        """Replace the full prompt text through one grouped edit."""

        self._edit_controller.finish_pending_key_edit_block(
            reason="replace_document_text"
        )
        state = self._source_state()
        self._edit_controller.begin_edit_block()
        try:
            command_result = self._dispatch_full_source_command(
                name="replace_document_text",
                text=text,
                cursor_position=min(state.cursor_position, len(text)),
                anchor_position=min(state.anchor_position, len(text)),
                exact_source=state.exact_source,
                record_undo=False,
                clear_history=False,
            )
            self._publish_full_source_result(
                command_result,
                previous_text=state.text,
                optimistic_prompt_state=None,
                schedule_geometry_reuse_warm_reason=(
                    "replace_document_text_with_prompt_state"
                ),
            )
        finally:
            self._edit_controller.end_edit_block()

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace full prompt text using a known semantic prompt snapshot."""

        self._edit_controller.finish_pending_key_edit_block(
            reason="replace_document_text_with_prompt_state"
        )
        state = self._source_state()
        self._edit_controller.begin_edit_block()
        try:
            command_result = self._dispatch_full_source_command(
                name="replace_document_text_with_prompt_state",
                text=text,
                cursor_position=min(state.cursor_position, len(text)),
                anchor_position=min(state.anchor_position, len(text)),
                exact_source=state.exact_source,
                record_undo=False,
                clear_history=False,
            )
            self._publish_full_source_result(
                command_result,
                previous_text=state.text,
                optimistic_prompt_state=PromptOptimisticPromptState(
                    document_view=document_view,
                    render_plan=render_plan,
                ),
            )
        finally:
            self._edit_controller.end_edit_block()

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[TPayload]:
        """Execute one prepared autocomplete acceptance through commands."""

        self._edit_controller.finish_pending_key_edit_block(
            reason="autocomplete_acceptance"
        )
        command = build_autocomplete_acceptance_command(
            acceptance,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
            structured_text_mutations=self._structured_text_mutations,
        )
        return self._dispatch_source_replacement_command(
            command,
            previous_text=self._source_text_provider(),
            origin=PromptSourceEditOrigin.AUTOCOMPLETE,
        )

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[TPayload]:
        """Execute one prepared diagnostic action through commands."""

        command = build_diagnostic_action_command(
            action,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
        )
        self._edit_controller.finish_pending_key_edit_block(reason="diagnostic_action")
        self._edit_controller.begin_edit_block(finish_typing=False)
        try:
            command_result = cast(
                PromptDiagnosticCommandResult[TPayload],
                self._edit_controller.dispatch_command(command),
            )
            applications = tuple(
                self._source_replacement_application(
                    source_change=source_change,
                    previous_text=source_change.previous_snapshot.source_text,
                    origin=PromptSourceEditOrigin.PROGRAMMATIC,
                    undo_availability_change=source_change.undo_availability_change,
                )
                for source_change in command_result.source_changes
            )
            self._publish_result(command_result, applications)
            return command_result
        finally:
            self._edit_controller.end_edit_block()

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[TPayload]:
        """Execute one prepared weight action through commands."""

        command = build_weight_action_command(
            request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            record_undo=False,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
        )
        self._edit_controller.finish_pending_key_edit_block(reason="weight_action")
        self._edit_controller.begin_edit_block(finish_typing=False)
        try:
            command_result = cast(
                PromptWeightCommandResult[TPayload],
                self._edit_controller.dispatch_command(command),
            )
            self._publish_semantic_command_result(command_result)
            return command_result
        finally:
            self._edit_controller.end_edit_block()

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[TPayload]:
        """Execute one prepared reorder commit through commands."""

        command = build_reorder_layout_commit_command(
            request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            record_undo=False,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
        )
        self._edit_controller.finish_pending_key_edit_block(reason="reorder_commit")
        self._edit_controller.begin_edit_block(finish_typing=False)
        try:
            command_result = cast(
                PromptReorderCommandResult[TPayload],
                self._edit_controller.dispatch_command(command),
            )
            self._publish_semantic_command_result(command_result)
            return command_result
        finally:
            self._edit_controller.end_edit_block()

    def execute_prepared_danbooru_import(
        self,
        request: PromptPreparedDanbooruImportRequest[TPayload],
    ) -> PromptPasteImportCommandResult[TPayload]:
        """Execute one prepared Danbooru import insertion through commands."""

        command = build_prepared_danbooru_import_command(
            request,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            record_undo=True,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
            structured_text_mutations=self._structured_text_mutations,
        )
        self._edit_controller.finish_pending_key_edit_block(
            reason="danbooru_import_result"
        )
        previous_text = self._source_text_provider()
        command_result = cast(
            PromptPasteImportCommandResult[TPayload],
            self._edit_controller.dispatch_command(command),
        )
        self._publish_source_replacement_result(
            command_result,
            previous_text=previous_text,
            origin=PromptSourceEditOrigin.PASTE,
        )
        return command_result

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[TPayload]:
        """Execute one prepared source replacement through commands."""

        self._edit_controller.finish_pending_key_edit_block(reason=command_name)
        return self._replace_source_range_from_replacement(
            replacement,
            command_name=command_name,
        )

    def execute_trigger_word_insertion(
        self,
        request: PromptTriggerWordInsertionRequest,
    ) -> PromptCommandResult[TPayload]:
        """Execute one identity-safe trigger-word insertion command."""

        self._edit_controller.finish_pending_key_edit_block(
            reason="lora_insert_trigger_words"
        )
        command = build_trigger_word_insertion_command(
            request,
            normalizer=self._normalizer,
            exact_source=self._source_state().exact_source,
            undo_snapshot=self._edit_controller.current_undo_snapshot(),
            structured_text_mutations=self._structured_text_mutations,
        )
        return self._dispatch_source_replacement_command(
            command,
            previous_text=self._source_text_provider(),
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
        )

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
    ) -> PromptCommandResult[TPayload]:
        """Replace one source range for viewport-local editing paths."""

        return self._replace_source_range_from_replacement(
            PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=start, end=end),
                replacement_text=replacement_text,
                origin=origin,
                exact_source=self._source_state().exact_source,
                record_undo=record_undo,
            ),
            command_name=command_name,
        )

    def _source_state(self) -> _RouterSourceState:
        """Read the current source state through injected live providers."""

        return _RouterSourceState(
            text=self._source_text_provider(),
            cursor_position=self._cursor_position_provider(),
            anchor_position=self._anchor_position_provider(),
            exact_source=self._exact_source_provider(),
        )

    def _replace_full_source_text(
        self,
        text: str,
        *,
        cursor_position: int,
        anchor_position: int,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
        trace_name: str,
        reset_scroll_to_top: bool,
    ) -> None:
        """Replace all source text while applying the requested undo policy."""

        self._edit_controller.finish_pending_key_edit_block(reason=trace_name)
        command_result = self._dispatch_full_source_command(
            name=trace_name,
            text=text,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            exact_source=exact_source,
            record_undo=record_undo,
            clear_history=clear_history,
        )
        source_change = command_result.source_change
        if source_change is None:
            self._edit_controller.emit_undo_availability_change(
                command_result.undo_availability_change
            )
            return
        if not source_change.source_changed:
            self._edit_controller.emit_undo_availability_change(
                command_result.undo_availability_change
            )
            return
        self._publish_full_source_result(
            command_result,
            previous_text=source_change.previous_snapshot.source_text,
            optimistic_prompt_state=None,
            undo_availability_change=command_result.undo_availability_change,
            reset_scroll_to_top=reset_scroll_to_top,
        )

    def _dispatch_full_source_command(
        self,
        *,
        name: str,
        text: str,
        cursor_position: int,
        anchor_position: int,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
    ) -> PromptCommandResult[TPayload]:
        """Dispatch one full-source command through the edit controller."""

        return self._edit_controller.dispatch_command(
            PromptReplaceFullSourceCommand(
                name=name,
                text=text,
                cursor_position=cursor_position,
                anchor_position=anchor_position,
                normalizer=self._normalizer,
                exact_source=exact_source,
                record_undo=record_undo,
                clear_history=clear_history,
                undo_snapshot=self._edit_controller.current_undo_snapshot(),
            )
        )

    def _replace_source_range_from_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[TPayload]:
        """Dispatch and publish one source-range replacement command."""

        previous_text = self._source_text_provider()
        command_result = self._edit_controller.dispatch_command(
            PromptReplaceSourceRangeCommand(
                name=command_name,
                replacement=replacement,
                normalizer=self._normalizer,
                undo_snapshot=self._edit_controller.current_undo_snapshot(),
            )
        )
        self._publish_source_replacement_result(
            command_result,
            previous_text=previous_text,
            origin=replacement.origin,
        )
        return command_result

    def _dispatch_source_replacement_command(
        self,
        command: PromptEditorCommand[TPayload],
        *,
        previous_text: str,
        origin: PromptSourceEditOrigin,
    ) -> PromptCommandResult[TPayload]:
        """Dispatch a prepared source-replacement command and publish its edit."""

        command_result = self._edit_controller.dispatch_command(command)
        self._publish_source_replacement_result(
            command_result,
            previous_text=previous_text,
            origin=origin,
        )
        return command_result

    def _publish_source_replacement_result(
        self,
        command_result: PromptCommandResult[TPayload],
        *,
        previous_text: str,
        origin: PromptSourceEditOrigin,
    ) -> None:
        """Publish one source-replacement result through the mutation sink."""

        source_change = command_result.source_change
        if source_change is None:
            self._edit_controller.emit_undo_availability_change(
                command_result.undo_availability_change
            )
            return
        self._publish_result(
            command_result,
            (
                self._source_replacement_application(
                    source_change=source_change,
                    previous_text=previous_text,
                    origin=origin,
                    undo_availability_change=command_result.undo_availability_change,
                ),
            ),
        )

    def _publish_semantic_command_result(
        self,
        command_result: PromptWeightCommandResult[TPayload]
        | PromptReorderCommandResult[TPayload],
    ) -> None:
        """Publish one semantic command result carrying prepared prompt state."""

        source_change = command_result.source_change
        if source_change is None:
            return
        optimistic_prompt_state = (
            PromptOptimisticPromptState(
                document_view=command_result.mutation.document_view,
                render_plan=command_result.render_plan,
            )
            if command_result.mutation is not None
            and command_result.render_plan is not None
            else None
        )
        self._publish_full_source_result(
            command_result,
            previous_text=source_change.previous_snapshot.source_text,
            optimistic_prompt_state=optimistic_prompt_state,
        )

    def _publish_full_source_result(
        self,
        command_result: PromptCommandResult[TPayload],
        *,
        previous_text: str,
        optimistic_prompt_state: PromptOptimisticPromptState | None,
        undo_availability_change: PromptUndoAvailabilityChange | None = None,
        reset_scroll_to_top: bool = False,
        schedule_geometry_reuse_warm_reason: str | None = None,
    ) -> None:
        """Publish one full-source command result through the mutation sink."""

        source_change = command_result.source_change
        if source_change is None:
            return
        source_edit = source_change.source_edit
        self._publish_result(
            command_result,
            (
                PromptProjectionSourceChangeApplication(
                    source_change=source_change,
                    previous_source_text=previous_text,
                    origin=PromptSourceEditOrigin.PROGRAMMATIC,
                    mode=PromptProjectionSourceApplicationMode.FULL_SOURCE,
                    optimistic_prompt_state=optimistic_prompt_state,
                    source_edit_start=None
                    if source_edit is None
                    else source_edit.start,
                    source_edit_end=None if source_edit is None else source_edit.end,
                    source_edit_replacement_text=None
                    if source_edit is None
                    else source_edit.replacement_text,
                    reset_scroll_to_top=reset_scroll_to_top,
                    schedule_geometry_reuse_warm_reason=(
                        schedule_geometry_reuse_warm_reason
                    ),
                    signal_intent=PromptMutationSignalIntent(
                        undo_availability_change=undo_availability_change,
                        emit_text_changed=True,
                    ),
                ),
            ),
        )

    def _source_replacement_application(
        self,
        *,
        source_change: PromptEditingSessionSourceChange[TPayload],
        previous_text: str,
        origin: PromptSourceEditOrigin,
        undo_availability_change: PromptUndoAvailabilityChange | None,
    ) -> PromptProjectionSourceChangeApplication[TPayload]:
        """Build one source-replacement projection application."""

        return PromptProjectionSourceChangeApplication(
            source_change=source_change,
            previous_source_text=previous_text,
            origin=origin,
            mode=PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT,
            signal_intent=PromptMutationSignalIntent(
                undo_availability_change=undo_availability_change,
                emit_text_changed=source_change.source_changed,
                emit_cursor_position_changed=True,
            ),
        )

    def _publish_result(
        self,
        outcome: PromptCommandResult[TPayload],
        applications: tuple[PromptProjectionSourceChangeApplication[TPayload], ...],
    ) -> None:
        """Publish committed source applications when any command mutated source."""

        if not applications:
            return
        self._mutation_sink.apply_edit_controller_result(
            PromptEditControllerResult(
                outcome=outcome,
                source_applications=applications,
            )
        )


__all__ = ["PromptEditCommandRouter"]
