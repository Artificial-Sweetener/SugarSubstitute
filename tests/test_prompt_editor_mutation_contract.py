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

"""Tests for the Phase 21.1 prompt editor mutation result contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSourceNormalizationService,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptReplaceSourceRangeCommand,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptEditController,
    PromptEditControllerResult,
    PromptMutationSignalIntent,
    PromptOptimisticPromptState,
    PromptProjectionRestoreApplication,
    PromptProjectionSourceChangeApplication,
)


def _session(source_text: str) -> PromptEditingSession[str]:
    """Return one editing session for mutation-contract tests."""

    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=len(source_text),
            anchor_position=len(source_text),
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return a passive undo snapshot for mutation-contract tests."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=source_text,
    )


def _empty_prompt_state(source_text: str) -> PromptOptimisticPromptState:
    """Return prepared prompt state without involving feature command requests."""

    return PromptOptimisticPromptState(
        document_view=PromptDocumentView(
            source_text=source_text,
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            has_trailing_comma=False,
        ),
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
    )


@dataclass(slots=True)
class _RecordingMutationSink:
    """Record edit-controller results using only the public sink protocol."""

    results: list[PromptEditControllerResult[str, PromptCommandResult[str]]]

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[str, PromptCommandResult[str]],
    ) -> None:
        """Store one projection mutation result."""

        self.results.append(result)


@dataclass(slots=True)
class _UndoPayloadProvider:
    """Provide stable payload data for edit-controller tests."""

    restoration_payload: str | None = "projection"
    comparison_payload: str | None = "comparison"

    def undo_restoration_payload(self) -> str | None:
        """Return passive restoration payload data."""

        return self.restoration_payload

    def undo_comparison_payload(self) -> str | None:
        """Return passive comparison payload data."""

        return self.comparison_payload


@dataclass(slots=True)
class _AvailabilitySink:
    """Record undo/redo availability emissions from a controller."""

    undo_values: list[bool]
    redo_values: list[bool]

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record one undo availability emission."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record one redo availability emission."""

        self.redo_values.append(available)


@dataclass(slots=True)
class _PendingKeyFlusher:
    """Record pending key block flush requests."""

    typing_reasons: list[str]
    pending_reasons: list[str]

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Record one typing-only flush."""

        self.typing_reasons.append(reason)

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Record one full pending-key flush."""

        self.pending_reasons.append(reason)


def _controller(
    source_text: str,
) -> tuple[
    PromptEditController[str],
    _AvailabilitySink,
    _PendingKeyFlusher,
]:
    """Return a controller and recording collaborators for tests."""

    availability_sink = _AvailabilitySink(undo_values=[], redo_values=[])
    pending_flusher = _PendingKeyFlusher(typing_reasons=[], pending_reasons=[])
    return (
        PromptEditController(
            session=_session(source_text),
            undo_payload_provider=_UndoPayloadProvider(),
            availability_signal_sink=availability_sink,
            pending_key_flusher=pending_flusher,
        ),
        availability_sink,
        pending_flusher,
    )


def test_edit_controller_owns_source_identity_and_undo_snapshot_capture() -> None:
    """Source identity and undo snapshots should come from the controller."""

    controller, _availability_sink, _pending_flusher = _controller("alpha")

    identity = controller.prompt_command_source_identity()
    snapshot = controller.current_undo_snapshot()

    assert identity.source_revision == 0
    assert identity.source_length == 5
    assert snapshot.source_text == "alpha"
    assert snapshot.source_revision == 0
    assert snapshot.restoration_payload == "projection"
    assert snapshot.comparison_payload == "comparison"


def test_edit_controller_emits_availability_once_per_transition() -> None:
    """Undo/redo availability should emit once for each actual transition."""

    controller, availability_sink, _pending_flusher = _controller("alpha")
    command = PromptReplaceSourceRangeCommand(
        name="append_text",
        replacement=PromptCommandTextReplacement(
            source_range=PromptCommandSourceRange(start=5, end=5),
            replacement_text=" beta",
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            exact_source=True,
            record_undo=True,
        ),
        normalizer=PromptSourceNormalizationService(),
        undo_snapshot=controller.current_undo_snapshot(),
    )

    result = controller.execute_command(command)

    assert result.outcome.status == "applied"
    assert availability_sink.undo_values == [True]
    assert availability_sink.redo_values == []


def test_edit_controller_owns_edit_block_and_pending_key_lifecycle() -> None:
    """Edit blocks and pending-key completion route through the controller."""

    controller, availability_sink, pending_flusher = _controller("alpha")

    controller.begin_edit_block()
    controller.end_edit_block()
    controller.finish_pending_key_edit_block(reason="context_menu")

    assert pending_flusher.typing_reasons == ["begin_edit_block"]
    assert pending_flusher.pending_reasons == ["context_menu"]
    assert availability_sink.undo_values == []
    assert availability_sink.redo_values == []


def test_source_change_application_carries_committed_edit_without_command_builder() -> (
    None
):
    """Committed source edits should be sufficient for a projection sink."""

    session = _session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    outcome = PromptCommandResult.from_source_change("append_text", source_change)
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(
            undo_availability_change=outcome.undo_availability_change,
            emit_text_changed=True,
            emit_cursor_position_changed=True,
        ),
    )
    result = PromptEditControllerResult(
        outcome=outcome,
        source_applications=(application,),
    )
    sink = _RecordingMutationSink(results=[])

    sink.apply_edit_controller_result(result)

    recorded = sink.results[0]
    assert recorded.outcome.status == "applied"
    assert recorded.source_applications == (application,)
    assert application.source_change.next_snapshot.source_text == "alpha beta"
    assert application.previous_source_text == "alpha"
    assert application.signal_intent.emit_text_changed


def test_rejected_and_noop_outcomes_do_not_require_projection_application() -> None:
    """Rejected and no-op commands should not force source application work."""

    rejected = PromptEditControllerResult[str, PromptCommandResult[str]](
        outcome=PromptCommandResult.rejected("stale_acceptance", reason="stale_source")
    )
    noop = PromptEditControllerResult[str, PromptCommandResult[str]](
        outcome=PromptCommandResult.noop(
            "select_all_when_empty",
            cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
            reason="empty_source",
        )
    )

    assert rejected.outcome.status == "rejected"
    assert rejected.source_applications == ()
    assert noop.outcome.status == "noop"
    assert noop.source_applications == ()


def test_optimistic_prompt_state_is_passive_projection_data() -> None:
    """Optimistic semantic adoption should carry snapshots, not feature requests."""

    session = _session("alpha")
    source_change = session.replace_source_range(
        start=0,
        end=5,
        replacement_text="beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    optimistic_prompt_state = _empty_prompt_state("beta")
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        optimistic_prompt_state=optimistic_prompt_state,
    )

    assert application.optimistic_prompt_state is optimistic_prompt_state
    document_view = cast(
        PromptDocumentView,
        application.optimistic_prompt_state.document_view,
    )
    render_plan = cast(
        PromptSyntaxRenderPlan,
        application.optimistic_prompt_state.render_plan,
    )
    assert document_view.source_text == "beta"
    assert render_plan.renderer_views == ()


def test_restore_application_carries_undo_restore_without_command_details() -> None:
    """Undo and redo restore paths should have a typed projection application."""

    session = _session("alpha")
    session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    restore_result = session.undo(_undo_snapshot("alpha beta"))

    assert restore_result is not None
    application = PromptProjectionRestoreApplication(
        restore_result=restore_result,
        signal_intent=PromptMutationSignalIntent(
            undo_availability_change=restore_result.availability_change,
            emit_text_changed=True,
            emit_cursor_position_changed=True,
        ),
    )
    result: PromptEditControllerResult[str, PromptCommandResult[str]] = (
        PromptEditControllerResult(
            outcome=PromptCommandResult.completed("undo_restore"),
            source_applications=(application,),
        )
    )

    assert result.source_applications == (application,)
    assert application.restore_result.snapshot.source_text == "alpha"
    assert application.restore_result.source_snapshot.source_text == "alpha"
    assert application.signal_intent.undo_availability_change is not None
