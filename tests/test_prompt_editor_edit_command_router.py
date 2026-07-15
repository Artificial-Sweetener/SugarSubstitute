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

"""Tests for the prompt editor feature command mutation router."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisContentAction,
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptMutationService,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
    PromptSourceNormalizationService,
    PromptSpellingDiagnosticPayload,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
    PromptCommandSourceRange,
    PromptPreparedDanbooruImportRequest,
    PromptReorderLayoutCommitRequest,
    PromptSpellingReplacementDiagnosticAction,
    PromptTagAutocompleteAcceptance,
    PromptWeightActionRequest,
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
    PromptProjectionSourceApplicationMode,
    PromptProjectionSourceChangeApplication,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptEditCommandRouter,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


@dataclass(slots=True)
class _PayloadProvider:
    """Provide passive undo payloads for router tests."""

    session: PromptEditingSession[str]

    def undo_restoration_payload(self) -> str:
        """Return the current source text as restoration payload."""

        return self.session.source_text

    def undo_comparison_payload(self) -> str:
        """Return the current source text as comparison payload."""

        return self.session.source_text


@dataclass(slots=True)
class _AvailabilitySink:
    """Record undo/redo availability emissions."""

    undo_values: list[bool] = field(default_factory=list)
    redo_values: list[bool] = field(default_factory=list)

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record one undo availability transition."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record one redo availability transition."""

        self.redo_values.append(available)


@dataclass(slots=True)
class _MutationSink:
    """Record projection mutation results published by the router."""

    results: list[PromptEditControllerResult[str, object]] = field(default_factory=list)

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[str, object],
    ) -> None:
        """Record one router-published mutation result."""

        self.results.append(result)


@dataclass(slots=True)
class _Harness:
    """Bundle one command-router test harness."""

    session: PromptEditingSession[str]
    router: PromptEditCommandRouter[str]
    sink: _MutationSink
    availability_sink: _AvailabilitySink


def _harness(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
    exact_source: bool = False,
) -> _Harness:
    """Return one router harness backed by a real editing session."""

    default_position = len(source_text)
    session = PromptEditingSession[str](
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=default_position
            if cursor_position is None
            else cursor_position,
            anchor_position=default_position
            if anchor_position is None
            else anchor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )
    availability_sink = _AvailabilitySink()
    edit_controller = PromptEditController[str](
        session=session,
        undo_payload_provider=_PayloadProvider(session),
        availability_signal_sink=availability_sink,
    )
    sink = _MutationSink()
    router = PromptEditCommandRouter[str](
        edit_controller=edit_controller,
        normalizer=PromptSourceNormalizationService(),
        mutation_sink=sink,
        source_text_provider=lambda: session.source_text,
        cursor_position_provider=lambda: session.cursor_position,
        anchor_position_provider=lambda: session.anchor_position,
        exact_source_provider=lambda: exact_source,
    )
    return _Harness(
        session=session,
        router=router,
        sink=sink,
        availability_sink=availability_sink,
    )


def _source_identity(session: PromptEditingSession[str]) -> PromptCommandSourceIdentity:
    """Return the current source identity for prepared command requests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Return the current session state as a passive undo snapshot."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        restoration_payload=session.source_text,
    )


def _spelling_diagnostic(start: int, end: int, word: str) -> PromptDiagnostic:
    """Return a spelling diagnostic over one source range."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{word}:{start}:{end}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        message=f"Unknown word: {word}",
        source_start=start,
        source_end=end,
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def _mutation_service() -> PromptMutationService:
    """Return a real prompt mutation service for semantic router tests."""

    return PromptMutationService()


def _syntax_service() -> PromptSyntaxService:
    """Return a real syntax service for semantic router tests."""

    return PromptSyntaxService(EmptyPromptWildcardCatalogGateway())


def _last_application(
    harness: _Harness,
) -> PromptProjectionSourceChangeApplication[str]:
    """Return the last published source application."""

    application = harness.sink.results[-1].source_applications[-1]
    assert isinstance(application, PromptProjectionSourceChangeApplication)
    return application


def test_router_replaces_viewport_source_range_without_surface_command_builder() -> (
    None
):
    """Viewport edits should publish source-replacement applications."""

    harness = _harness("alpha")

    result = harness.router.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        origin=PromptSourceEditOrigin.TYPED,
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == "alpha beta"
    assert application.mode is PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT
    assert application.previous_source_text == "alpha"
    assert application.origin is PromptSourceEditOrigin.TYPED


def test_router_full_source_replacement_publishes_full_source_application() -> None:
    """Full-source text replacement should publish a full-source application."""

    harness = _harness("alpha")

    harness.router.set_plain_text("beta")

    application = _last_application(harness)
    assert harness.session.source_text == "beta"
    assert application.mode is PromptProjectionSourceApplicationMode.FULL_SOURCE
    assert application.previous_source_text == "alpha"
    assert application.reset_scroll_to_top


def test_router_accepts_autocomplete_through_source_replacement_application() -> None:
    """Autocomplete acceptance should be command-built by the router."""

    harness = _harness("xx cat_", cursor_position=7)

    result = harness.router.execute_autocomplete_acceptance(
        PromptTagAutocompleteAcceptance(
            tag="cat_(animal)",
            prefix="cat_",
            word_start=3,
            word_end=7,
            active_tag_end=7,
            add_comma=True,
            source_identity=_source_identity(harness.session),
        )
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == r"xx cat \(animal\), "
    assert application.mode is PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT
    assert application.previous_source_text == "xx cat_"


def test_router_applies_diagnostic_actions_as_source_replacement_applications() -> None:
    """Diagnostic fixes should publish one application per source change."""

    harness = _harness("one typo ", cursor_position=len("one typo "))

    result = harness.router.execute_diagnostic_action(
        PromptSpellingReplacementDiagnosticAction(
            diagnostic=_spelling_diagnostic(4, 8, "typo"),
            replacement_text="type",
            source_identity=_source_identity(harness.session),
        )
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == "one type "
    assert len(result.source_changes) == 1
    assert application.mode is PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT


def test_router_weight_action_publishes_full_source_optimistic_application() -> None:
    """Weight commands should publish semantic prompt state with full-source edits."""

    harness = _harness("cat", cursor_position=3, anchor_position=0)

    result = harness.router.execute_weight_action(
        PromptWeightActionRequest(
            action=PromptAdjustEmphasisContentAction(
                content_start=0,
                content_end=3,
                delta=Decimal("0.05"),
            ),
            source_identity=_source_identity(harness.session),
            cursor_policy="preserve_cursor",
        ),
        mutation_service=_mutation_service(),
        syntax_service=_syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == "(cat:1.05)"
    assert application.mode is PromptProjectionSourceApplicationMode.FULL_SOURCE
    assert application.optimistic_prompt_state is not None


def test_router_reorder_action_publishes_full_source_optimistic_application() -> None:
    """Reorder commits should publish semantic prompt state with full-source edits."""

    harness = _harness("alpha, beta")

    result = harness.router.execute_reorder_action(
        PromptReorderLayoutCommitRequest(
            reorder_state=PromptReorderStateView(
                ordered_chip_indices=(1, 0),
                separator_slots=(", ",),
                has_trailing_comma=False,
            ),
            layout_view=PromptReorderLayoutView(
                rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
                gaps=(),
            ),
            selected_chip_index=1,
            source_identity=_source_identity(harness.session),
        ),
        mutation_service=_mutation_service(),
        syntax_service=_syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == "beta, alpha"
    assert application.mode is PromptProjectionSourceApplicationMode.FULL_SOURCE
    assert application.optimistic_prompt_state is not None


def test_router_prepared_danbooru_import_publishes_normalized_replacement() -> None:
    """Prepared Danbooru import should remain command-backed but scheduler-free."""

    harness = _harness("https://danbooru.donmai.us/posts/1")
    pasted_snapshot = _undo_snapshot(harness.session)

    result = harness.router.execute_prepared_danbooru_import(
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(
                0,
                len("https://danbooru.donmai.us/posts/1"),
            ),
            expected_pasted_text="https://danbooru.donmai.us/posts/1",
            import_text="tag one, tag two",
            pasted_undo_snapshot=pasted_snapshot,
        )
    )

    application = _last_application(harness)
    assert result.status == "applied"
    assert harness.session.source_text == "tag one, tag two"
    assert application.mode is PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT
    assert application.origin is PromptSourceEditOrigin.PASTE


def test_router_rejected_prepared_command_publishes_no_projection_application() -> None:
    """Rejected prepared imports should not publish projection work."""

    harness = _harness("edited text")

    result = harness.router.execute_prepared_danbooru_import(
        PromptPreparedDanbooruImportRequest(
            source_range=PromptCommandSourceRange(0, len("edited text")),
            expected_pasted_text="original url",
            import_text="tag one",
            pasted_undo_snapshot=_undo_snapshot(harness.session),
        )
    )

    assert result.status == "rejected"
    assert result.reason == "pasted_text_changed"
    assert harness.sink.results == []
