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

"""Tests for prompt interaction syntax-action orchestration."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptConsumeSyntaxAction,
    PromptDocumentService,
    PromptMutation,
    PromptMutationService,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSourceNormalizationService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    build_weight_action_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptWeightControlIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    prompt_interaction_controller,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


class MousePressEventDouble:
    """Provide the position consumed by controller mouse-press handling."""

    def __init__(self, position: object) -> None:
        """Store one deterministic event position."""

        self._position = position

    def position(self) -> object:
        """Return the configured viewport-local event position."""

        return self._position


class MutationServiceDouble:
    """Provide deterministic mutation responses for syntax-action tests."""

    def __init__(
        self,
        *,
        apply_syntax_action_result: PromptMutation | None = None,
    ) -> None:
        """Store the mutation value returned to the controller."""

        self.apply_syntax_action_result = apply_syntax_action_result
        self.adjust_calls: list[tuple[str, int, int, float]] = []
        self.apply_syntax_action_calls: list[tuple[str, object]] = []

    def adjust_emphasis(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        delta: float,
    ) -> PromptMutation:
        """Record unexpected legacy emphasis adjustment calls."""

        self.adjust_calls.append((text, selection_start, selection_end, delta))
        raise AssertionError("Syntax-action tests should use typed mutation actions.")

    def apply_syntax_action(self, text: str, action: object) -> PromptMutation | None:
        """Return the configured syntax-action result after recording the request."""

        self.apply_syntax_action_calls.append((text, action))
        return self.apply_syntax_action_result


class SyntaxActionEditorDouble(ControllerEditorDouble):
    """Provide editor command behavior required by syntax-action tests."""

    def __init__(
        self,
        *,
        clicked_cursor: MenuCursorDouble,
        current_cursor: MenuCursorDouble,
        text: str,
    ) -> None:
        """Initialize prompt text, command state, and projection call tracking."""

        super().__init__(
            clicked_cursor=clicked_cursor,
            current_cursor=current_cursor,
            text=text,
        )
        self.set_plain_text_calls: list[str] = []
        self.replace_document_text_calls: list[str] = []
        self.replace_document_text_with_prompt_state_calls: list[
            tuple[str, object, object]
        ] = []
        self.blocked_signals: list[bool] = []
        self.focus_calls = 0
        self.pulse_emphasis_feedback_calls: list[tuple[int, int]] = []
        self.transient_neutral_emphasis_calls: list[tuple[int, int]] = []
        self._emphasis_adjustment_session: PromptEmphasisAdjustmentSession | None = None
        self._transient_neutral_emphasis_range: tuple[int, int] | None = None
        self._transient_neutral_emphasis_owner: (
            PromptTransientNeutralEmphasisOwner | None
        ) = None
        self.emphasis_content_boundary_calls: list[tuple[int, int, bool]] = []
        self.executed_weight_requests: list[PromptWeightActionRequest] = []
        self._source_revision = 0

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute a prepared weight command against the fake source state."""

        self.executed_weight_requests.append(request)
        cursor = self.textCursor()
        cursor_state = PromptCursorState(
            cursor_position=cursor.position(),
            anchor_position=cursor.anchor(),
        )
        session = PromptEditingSession[object](
            source_text=self.toPlainText(),
            source_revision=self._source_revision,
            cursor_state=cursor_state,
            max_undo_states=20,
            max_redo_states=20,
        )
        command = build_weight_action_command(
            request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            record_undo=True,
            undo_snapshot=PromptUndoSnapshot[object](
                source_text=self.toPlainText(),
                cursor_state=cursor_state,
                source_revision=self._source_revision,
            ),
        )
        result = cast(
            PromptWeightCommandResult[object],
            PromptCommandDispatcher(session).execute(command),
        )
        source_change = result.source_change
        if source_change is not None:
            next_text = source_change.next_snapshot.source_text
            self._source_revision = source_change.next_snapshot.source_revision
            if result.mutation is not None and result.render_plan is not None:
                self.replace_document_text_with_prompt_state(
                    next_text,
                    document_view=result.mutation.document_view,
                    render_plan=result.render_plan,
                )
            else:
                self.replace_document_text(next_text)
        if result.cursor_state is not None:
            self.setTextCursor(
                MenuCursorDouble(
                    text=self.toPlainText(),
                    position=result.cursor_state.cursor_position,
                    anchor=result.cursor_state.anchor_position,
                )
            )
        return result

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the backing prompt text and keep cursors in sync."""

        super().setPlainText(text)
        self.set_plain_text_calls.append(text)

    def replace_document_text(self, text: str) -> None:
        """Replace the backing prompt text through the undo-safe surface hook."""

        self.setPlainText(text)
        self.replace_document_text_calls.append(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: object,
        render_plan: object,
    ) -> None:
        """Replace backing text through the prompt-state optimized hook."""

        self.setPlainText(text)
        self.replace_document_text_with_prompt_state_calls.append(
            (text, document_view, render_plan)
        )

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        """Record signal blocking requested by controller mutations."""

        self.blocked_signals.append(blocked)

    def setFocus(self) -> None:  # noqa: N802
        """Record focus restoration after inline control clicks."""

        self.focus_calls += 1

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Record transient emphasis feedback requests from the controller."""

        self.pulse_emphasis_feedback_calls.append((outer_start, outer_end))

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Record one active emphasis-adjustment session owned by the controller."""

        self._emphasis_adjustment_session = PromptEmphasisAdjustmentSession(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear the active emphasis-adjustment session."""

        self._emphasis_adjustment_session = None

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when present."""

        return self._emphasis_adjustment_session

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

        session = self._emphasis_adjustment_session
        if session is None:
            return None
        return (session.content_start, session.content_end)

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

        session = self._emphasis_adjustment_session
        if session is None:
            return False
        return (
            session.content_start == content_start
            and session.content_end == content_end
        )

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Record requests to project a temporary neutral emphasis shell."""

        self._transient_neutral_emphasis_range = (content_start, content_end)
        self._transient_neutral_emphasis_owner = owner
        self.transient_neutral_emphasis_calls.append((content_start, content_end))

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear any temporary neutral emphasis shell."""

        self._transient_neutral_emphasis_range = None
        self._transient_neutral_emphasis_owner = None

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Clear the transient shell only when overlay interaction owns it."""

        if (
            self._transient_neutral_emphasis_owner
            is PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            self.clear_transient_neutral_emphasis()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the currently tracked temporary neutral emphasis range."""

        return self._transient_neutral_emphasis_range

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the currently tracked temporary neutral shell."""

        return self._transient_neutral_emphasis_owner

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Record one projected emphasis-content boundary placement request."""

        self.emphasis_content_boundary_calls.append(
            (content_start, content_end, prefer_end)
        )
        caret_position = content_end if prefer_end else content_start
        self.textCursor().setPosition(caret_position)
        return True


class DocumentServiceDouble:
    """Provide a deterministic prompt-document service for syntax-action tests."""

    def __init__(self, document_service: PromptDocumentService, *, text: str) -> None:
        """Store the initial cached document view."""

        self.document_view = document_service.build_document_view(text)
        self.build_calls: list[str] = []

    def build_document_view(self, text: str) -> object:
        """Return the prebuilt document view for the expected starting text."""

        self.build_calls.append(text)
        assert text == self.document_view.source_text
        return self.document_view

    def emphasis_for_content_range(
        self,
        document_view: object,
        *,
        content_start: int,
        content_end: int,
    ) -> object | None:
        """Return the emphasis span matching one visible content range."""

        for span in getattr(document_view, "emphasis_spans"):
            if span.content_start == content_start and span.content_end == content_end:
                return cast(object, span)
        return None

    def emphasis_for_outer_range(
        self,
        document_view: object,
        *,
        outer_start: int,
        outer_end: int,
    ) -> object | None:
        """Return the emphasis span matching one exact outer shell range."""

        for span in getattr(document_view, "emphasis_spans"):
            if span.outer_start == outer_start and span.outer_end == outer_end:
                return cast(object, span)
        return None


def test_inline_emphasis_click_consumes_event_and_routes_typed_syntax_action() -> None:
    """Inline control clicks clear autocomplete and route one syntax action."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = _mutation(document_service, "(cat:1.10)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    clear_calls: list[str] = []
    syntax_renderers = syntax_renderer_double(action)
    editor = _editor("(cat:1.05)", position=3)
    controller = _controller(
        editor,
        autocomplete=_autocomplete_with_clear_calls(clear_calls),
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = _record_applied_mutations(applied_mutations)

    handled = controller.handle_mouse_press(MousePressEventDouble("hit-point"))

    assert handled is True
    assert syntax_renderers.syntax_action_calls == ["hit-point"]
    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.toPlainText() == "(cat:1.10)"
    assert editor.executed_weight_requests[0].action == action
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert mutation_service.adjust_calls == []


def test_inline_emphasis_click_returns_false_when_pointer_misses_renderer_actions() -> (
    None
):
    """Mouse presses that miss renderer actions fall through to normal editing."""

    mutation_service = MutationServiceDouble()
    clear_calls: list[str] = []
    syntax_renderers = syntax_renderer_double()
    editor = _editor("(cat:1.05)", position=3)
    controller = _controller(
        editor,
        autocomplete=_autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )

    handled = controller.handle_mouse_press(MousePressEventDouble("miss-point"))

    assert handled is False
    assert syntax_renderers.syntax_action_calls == ["miss-point"]
    assert clear_calls == []
    assert mutation_service.apply_syntax_action_calls == []
    assert editor.focus_calls == 0


def test_inline_emphasis_click_consumes_stale_target_without_fallback_mutation_path() -> (
    None
):
    """Control hits still consume clicks when the underlying span disappears."""

    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=None)
    clear_calls: list[str] = []
    editor = _editor("(cat:1.05)", position=3)
    controller = _controller(
        editor,
        autocomplete=_autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderer_double(action),
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = _record_applied_mutations(applied_mutations)

    handled = controller.handle_mouse_press(MousePressEventDouble("stale-point"))

    assert handled is True
    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.focus_calls == 1


def test_apply_syntax_action_can_consume_passive_actions_without_mutation() -> None:
    """The shared syntax-action path supports consume-only actions."""

    action = PromptConsumeSyntaxAction(syntax_kind="emphasis")
    mutation_service = MutationServiceDouble(apply_syntax_action_result=None)
    clear_calls: list[str] = []
    editor = _editor("(cat:1.05)", position=3)
    controller = _controller(
        editor,
        autocomplete=_autocomplete_with_clear_calls(clear_calls),
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.apply_syntax_action(action)

    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == []
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == []


def test_apply_syntax_action_reuses_mouse_click_mutation_path() -> None:
    """Host-overlay syntax actions route through the shared mutation path."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = _mutation(document_service, "(cat:1.10)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    clear_calls: list[str] = []
    editor = _editor("(cat:1.05)", position=3)
    controller = _controller(
        editor,
        autocomplete=_autocomplete_with_clear_calls(clear_calls),
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )
    applied_mutations: list[tuple[PromptMutation, bool]] = []
    controller._apply_mutation = _record_applied_mutations(applied_mutations)

    controller.apply_syntax_action(action)

    assert clear_calls == ["clear"]
    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert applied_mutations == []
    assert editor.toPlainText() == "(cat:1.10)"
    assert editor.executed_weight_requests[0].action == action
    assert editor.focus_calls == 1
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]


def test_apply_syntax_action_keeps_transient_neutral_shell_visible_after_unwrap() -> (
    None
):
    """Neutral unwrap keeps one temporary `1.00` shell visible for adjustment."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation = _mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = _editor("(cat:1.05)", position=2)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert editor.toPlainText() == "cat"
    assert editor.transient_neutral_emphasis_calls == [(0, 3)]
    assert editor.transient_neutral_emphasis_range() == (0, 3)
    assert editor.pulse_emphasis_feedback_calls == []


def test_apply_overlay_syntax_action_marks_transient_neutral_shell_as_overlay_owned() -> (
    None
):
    """Overlay-owned actions keep neutral emphasis alive independently of caret ownership."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation = _mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = _editor("(cat:1.05)", position=10)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.apply_overlay_syntax_action(action)

    assert editor.transient_neutral_emphasis_range() == (0, 3)
    assert (
        editor.transient_neutral_emphasis_owner()
        is PromptTransientNeutralEmphasisOwner.OVERLAY
    )


def test_apply_overlay_syntax_action_starts_overlay_emphasis_adjustment_session() -> (
    None
):
    """Overlay emphasis actions persist one shared overlay-owned session."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = _mutation(document_service, "(cat:1.10)", 1, 4)
    editor = _editor("(cat:1.05)", position=4)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )

    controller.apply_overlay_syntax_action(action)

    assert editor.emphasis_adjustment_session() == PromptEmphasisAdjustmentSession(
        owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        content_start=1,
        content_end=4,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )


def test_handle_key_release_clears_keyboard_owned_transient_neutral_emphasis() -> None:
    """Releasing Ctrl ends keyboard adjustment and removes keyboard-owned neutral deco."""

    editor = _editor("cat", position=3)
    controller = _controller(
        editor,
        mutation_service=cast(PromptMutationService, MutationServiceDouble()),
    )
    editor.show_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.KEYBOARD,
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )

    handled = controller.handle_key_release(_key_event(Qt.Key.Key_Control))

    assert handled is False
    assert editor.transient_neutral_emphasis_range() is None
    assert editor.emphasis_adjustment_session() is None


def test_handle_overlay_visible_token_changed_clears_overlay_owned_session_and_shell() -> (
    None
):
    """Losing overlay token ownership clears overlay-owned session state."""

    editor = _editor("cat", position=3)
    controller = _controller(
        editor,
        mutation_service=cast(PromptMutationService, MutationServiceDouble()),
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )
    editor.show_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.OVERLAY,
    )

    controller.handle_overlay_visible_token_changed(None)

    assert editor.emphasis_adjustment_session() is None
    assert editor.transient_neutral_emphasis_range() is None


def test_modify_emphasis_places_keyboard_neutral_caret_at_content_boundary() -> None:
    """Keyboard emphasis unwrap places the caret at the token content boundary."""

    document_service = PromptDocumentService()
    mutation = _mutation(document_service, "cat", 0, 3)
    editor = _editor("(cat:1.05)", position=4, anchor=1)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )

    controller.modify_emphasis(-0.05)

    assert editor.emphasis_content_boundary_calls == [(0, 3, True)]
    assert editor.emphasis_adjustment_session() == PromptEmphasisAdjustmentSession(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )


def test_apply_keyboard_emphasis_action_preserves_session_caret_boundary_preference() -> (
    None
):
    """Keyboard-session emphasis actions keep using the stored content boundary."""

    document_service = PromptDocumentService()
    mutation = _mutation(document_service, "cat", 0, 3)
    editor = _editor("(cat:1.05)", position=4, anchor=1)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=1,
        content_end=4,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )

    controller.modify_emphasis(-0.05)

    assert editor.emphasis_content_boundary_calls == [(0, 3, True)]


def test_apply_syntax_action_routes_exact_weight_actions_through_emphasis_path() -> (
    None
):
    """Exact-weight actions reuse the same no-selection emphasis-apply path."""

    document_service = PromptDocumentService()
    action = PromptSetEmphasisWeightAction(outer_start=0, outer_end=10, weight=1.20)
    mutation = _mutation(document_service, "(cat:1.20)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = _editor("(cat:1.05)", position=2)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert editor.toPlainText() == "(cat:1.20)"
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert editor.transient_neutral_emphasis_calls == []


def test_apply_syntax_action_keeps_transient_neutral_shell_after_exact_neutral_set() -> (
    None
):
    """Exact neutral sets preserve the transient `1.00` shell for continued editing."""

    document_service = PromptDocumentService()
    action = PromptSetEmphasisWeightContentAction(
        content_start=0,
        content_end=3,
        weight=1.00,
    )
    mutation = _mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = _editor("cat", position=2)
    controller = _controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("cat", action)]
    assert editor.toPlainText() == "cat"
    assert editor.transient_neutral_emphasis_calls == [(0, 3)]
    assert editor.transient_neutral_emphasis_range() == (0, 3)


def test_modify_emphasis_uses_typed_mutation_result_to_refresh_cached_state() -> None:
    """Controller emphasis edits adopt the mutation snapshot without local reparsing."""

    document_service = PromptDocumentService()
    initial_document_service = DocumentServiceDouble(document_service, text="cat")
    updated_document_view = document_service.build_document_view("(cat:1.05)")
    mutation_service = MutationServiceDouble(
        apply_syntax_action_result=PromptMutation(
            text="(cat:1.05)",
            selection_start=1,
            selection_end=4,
            document_view=updated_document_view,
        )
    )
    editor = _editor("cat", position=3, anchor=0)
    syntax_renderers = syntax_renderer_double()
    controller = _controller(
        editor,
        document_service=cast(PromptDocumentService, initial_document_service),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )

    controller.modify_emphasis(0.05)

    assert initial_document_service.build_calls == ["cat"]
    assert mutation_service.apply_syntax_action_calls == [
        (
            "cat",
            PromptAdjustEmphasisContentAction(
                content_start=0,
                content_end=3,
                delta=0.05,
            ),
        )
    ]
    assert mutation_service.adjust_calls == []
    assert editor.toPlainText() == "(cat:1.05)"
    assert editor.replace_document_text_calls == []
    assert len(editor.replace_document_text_with_prompt_state_calls) == 1
    replaced_text, replaced_document_view, replaced_render_plan = (
        editor.replace_document_text_with_prompt_state_calls[0]
    )
    assert replaced_text == "(cat:1.05)"
    assert replaced_document_view is updated_document_view
    assert replaced_render_plan is syntax_renderers.prompt_state_calls[-1][1]
    assert editor.textCursor().selectionStart() == 4
    assert editor.textCursor().selectionEnd() == 4
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert controller.document_view is updated_document_view
    assert len(controller.syntax_render_plan.syntax_spans) == 1
    assert controller.active_syntax_span == updated_document_view.syntax_spans[0]


def _controller(
    editor: SyntaxActionEditorDouble,
    *,
    autocomplete: object | None = None,
    document_service: PromptDocumentService | None = None,
    mutation_service: PromptMutationService | None = None,
    syntax_renderers: SyntaxRendererCoordinatorDouble | None = None,
) -> Any:
    """Build a prompt interaction controller for one syntax-action scenario."""

    return prompt_interaction_controller(
        editor,
        autocomplete=autocomplete or autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers or syntax_renderer_double(),
        document_service=document_service or PromptDocumentService(),
        mutation_service=mutation_service or PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )


def _editor(
    text: str, *, position: int, anchor: int | None = None
) -> SyntaxActionEditorDouble:
    """Return a syntax-action editor double with matching click and caret cursors."""

    return SyntaxActionEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=position, anchor=anchor),
        current_cursor=MenuCursorDouble(text=text, position=position, anchor=anchor),
        text=text,
    )


def _mutation(
    document_service: PromptDocumentService,
    text: str,
    selection_start: int,
    selection_end: int,
) -> PromptMutation:
    """Return a mutation carrying a document view for the supplied text."""

    return PromptMutation(
        text=text,
        selection_start=selection_start,
        selection_end=selection_end,
        document_view=document_service.build_document_view(text),
    )


def _autocomplete_with_clear_calls(clear_calls: list[str]) -> SimpleNamespace:
    """Return an autocomplete double that records clear requests."""

    return SimpleNamespace(
        handle_key_press=lambda _event: False,
        refresh_for_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: clear_calls.append("clear"),
        refresh_geometry=lambda: None,
    )


def _record_applied_mutations(
    applied_mutations: list[tuple[PromptMutation, bool]],
) -> object:
    """Return an `_apply_mutation` replacement that records direct applications."""

    def apply_mutation_double(
        result: PromptMutation,
        *,
        block_signals: bool = False,
        render_plan: object | None = None,
    ) -> None:
        _ = render_plan
        applied_mutations.append((result, block_signals))

    return apply_mutation_double


def _key_event(
    key: int,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> SimpleNamespace:
    """Return the minimal key-event shape consumed by controller tests."""

    return SimpleNamespace(
        key=lambda: key,
        modifiers=lambda: modifiers,
        text=lambda: text,
    )


def test_prompt_interaction_controller_removes_old_flyout_entry_points() -> None:
    """The interaction controller no longer exposes retired flyout entry points."""

    mod = importlib.import_module(
        "substitute.presentation.editor.prompt_editor.interactions.controller"
    )

    assert hasattr(mod.PromptInteractionController, "handle_mouse_press")
    assert not hasattr(mod.PromptInteractionController, "show_emphasis_flyout")
    assert not hasattr(mod.PromptInteractionController, "handle_context_menu")
