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

"""Tests for prompt reorder commit command routing."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptMutation,
    PromptMutationService,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptSourceNormalizationService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    build_reorder_layout_commit_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptEditorInteractionMode,
    SegmentReorderSession,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    autocomplete_double,
    prompt_interaction_controller,
    reorder_state_for_indices,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


def test_commit_and_close_segment_overlay_routes_reorder_through_command() -> None:
    """Overlay commit delegates source mutation through the reorder command."""

    document_service = PromptDocumentService()
    mutation = PromptMutation(
        text="beta, alpha",
        selection_start=None,
        selection_end=None,
        document_view=document_service.build_document_view("beta, alpha"),
    )
    mutation_service = ReorderMutationService(reorder_result=mutation)
    editor = CommandEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=0),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=0),
        text="alpha, beta",
    )
    controller = _controller_for_commit(
        editor,
        document_service=document_service,
        mutation_service=mutation_service,
    )
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )
    overlay = OverlayDouble(
        [1, 0],
        active_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        current_layout_view=committed_layout_view,
    )
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER

    controller._reorder.commit_and_close_segment_overlay()

    assert mutation_service.reorder_layout_calls == [
        ("alpha, beta", reorder_state_for_indices((1, 0)), 1)
    ]
    assert editor.executed_reorder_requests == [
        PromptReorderLayoutCommitRequest(
            reorder_state=reorder_state_for_indices((1, 0)),
            layout_view=committed_layout_view,
            selected_chip_index=1,
        )
    ]
    assert editor.toPlainText() == "beta, alpha"
    assert editor.set_plain_text_calls == ["beta, alpha"]
    assert editor.replace_document_text_calls == []
    assert len(editor.replace_document_text_with_prompt_state_calls) == 1
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert controller.segment_overlay is None


def test_commit_and_close_segment_overlay_restores_caret_relative_to_moved_chip_after_drag_commit() -> (
    None
):
    """Overlay commit preserves the caret offset inside the moved chip."""

    document_service = PromptDocumentService()
    mutation = PromptMutation(
        text="beta, alpha",
        selection_start=0,
        selection_end=4,
        document_view=document_service.build_document_view("beta, alpha"),
    )
    mutation_service = ReorderMutationService(reorder_result=mutation)
    editor = CommandEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        current_cursor=MenuCursorDouble(text="alpha, beta", position=7),
        text="alpha, beta",
    )
    controller = _controller_for_commit(
        editor,
        document_service=document_service,
        mutation_service=mutation_service,
    )
    committed_layout_view = PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(1, 0)),),
        gaps=(),
    )
    overlay = OverlayDouble(
        [1, 0],
        active_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        current_layout_view=committed_layout_view,
    )
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
    controller._reorder._session_controller.replace_session(
        SegmentReorderSession(
            is_active=True,
            original_ordered_indices=(0, 1),
            current_ordered_indices=(1, 0),
            active_segment_index=1,
            selection_start=7,
            selection_end=7,
            selection_start_offset_within_active_chip=0,
            selection_end_offset_within_active_chip=0,
            has_reordered=True,
        )
    )

    controller._reorder.commit_and_close_segment_overlay()

    assert editor.toPlainText() == "beta, alpha"
    assert editor.textCursor().selectionStart() == 0
    assert editor.textCursor().selectionEnd() == 0
    assert overlay.closed == 1
    assert overlay.deleted == 1
    assert controller.segment_overlay is None


def test_commit_and_close_segment_overlay_forwards_typed_gap_drop_target() -> None:
    """Overlay commit preserves typed gap drop targets through the controller seam."""

    document_service = PromptDocumentService()
    mutation = PromptMutation(
        text="alpha,\n\ngamma,\n\n\nbeta",
        selection_start=None,
        selection_end=None,
        document_view=document_service.build_document_view(
            "alpha,\n\ngamma,\n\n\nbeta"
        ),
    )
    mutation_service = ReorderMutationService(reorder_result=mutation)
    editor = CommandEditorDouble(
        clicked_cursor=MenuCursorDouble(text="alpha,\n\n\n\n\nbeta, gamma", position=0),
        current_cursor=MenuCursorDouble(
            text="alpha,\n\n\n\n\nbeta, gamma",
            position=0,
        ),
        text="alpha,\n\n\n\n\nbeta, gamma",
    )
    controller = _controller_for_commit(
        editor,
        document_service=document_service,
        mutation_service=mutation_service,
    )
    committed_layout_view = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(2, 1)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=",\n\n",
                blank_line_count=1,
            ),
        ),
    )
    overlay = OverlayDouble(
        [0, 2, 1],
        active_segment_index=2,
        drop_target=PromptGapBlankLineDropTarget(gap_index=0, blank_line_index=1),
        current_layout_view=committed_layout_view,
    )
    controller._reorder._segment_overlay = overlay
    controller._reorder._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER

    controller._reorder.commit_and_close_segment_overlay()

    assert mutation_service.reorder_layout_calls == [
        (
            "alpha,\n\n\n\n\nbeta, gamma",
            reorder_state_for_indices((0, 2, 1)),
            2,
        )
    ]
    assert editor.executed_reorder_requests == [
        PromptReorderLayoutCommitRequest(
            reorder_state=reorder_state_for_indices((0, 2, 1)),
            layout_view=committed_layout_view,
            selected_chip_index=2,
        )
    ]
    assert editor.toPlainText() == "alpha,\n\ngamma,\n\n\nbeta"


class ReorderMutationService:
    """Provide deterministic reorder mutations for commit tests."""

    def __init__(self, *, reorder_result: PromptMutation) -> None:
        """Store the mutation returned to command execution."""

        self.reorder_result = reorder_result
        self.reorder_layout_calls: list[tuple[str, object, int | None]] = []

    def reorder_state(
        self,
        text: str,
        *,
        reorder_state: object,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Return the configured state-commit mutation after recording the request."""

        self.reorder_layout_calls.append((text, reorder_state, selected_chip_index))
        return self.reorder_result


class CommandEditorDouble(ControllerEditorDouble):
    """Execute reorder commands against the fake source state."""

    def __init__(
        self,
        *,
        clicked_cursor: MenuCursorDouble,
        current_cursor: MenuCursorDouble,
        text: str,
    ) -> None:
        """Initialize editor source, call tracking, and command revision state."""

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
        self._source_revision = 0

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the backing prompt text and record the change."""

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

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        **kwargs: object,
    ) -> PromptReorderCommandResult[object]:
        """Execute a prepared reorder command against the fake source state."""

        mutation_service = cast(PromptMutationService, kwargs["mutation_service"])
        resolved_syntax_service = cast(PromptSyntaxService, kwargs["syntax_service"])
        syntax_profile = cast(PromptSyntaxProfile, kwargs["syntax_profile"])
        self.executed_reorder_requests.append(request)
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
        command = build_reorder_layout_commit_command(
            request,
            mutation_service=mutation_service,
            syntax_service=resolved_syntax_service,
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
            PromptReorderCommandResult[object],
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


def _controller_for_commit(
    editor: CommandEditorDouble,
    *,
    document_service: PromptDocumentService,
    mutation_service: ReorderMutationService,
) -> Any:
    """Build a reorder controller for commit command tests."""

    return prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderer_double(),
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
