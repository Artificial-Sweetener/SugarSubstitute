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

"""Tests for Phase 3.5 prompt editor weight commands."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from substitute.application.prompt_editor import (
    PromptAdjustEmphasisContentAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptMutationService,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
    PromptSourceNormalizationService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    build_weight_action_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for weight command tests."""

    default_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=(
                default_position if cursor_position is None else cursor_position
            ),
            anchor_position=default_position
            if anchor_position is None
            else anchor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Return the current session state as a passive undo snapshot."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        restoration_payload=session.source_text,
    )


def _source_identity(session: PromptEditingSession[str]) -> PromptCommandSourceIdentity:
    """Return the current source identity for stale-command tests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def _execute_weight_request(
    session: PromptEditingSession[str],
    request: PromptWeightActionRequest,
) -> PromptWeightCommandResult[str]:
    """Execute one weight command request through the real dispatcher."""

    command = build_weight_action_command(
        request,
        mutation_service=PromptMutationService(),
        syntax_service=PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    return cast(
        PromptWeightCommandResult[str],
        PromptCommandDispatcher(session).execute(command),
    )


def test_emphasis_content_command_applies_through_editing_session() -> None:
    """Content emphasis commands should mutate source through the session owner."""

    session = _session("cat", cursor_position=3, anchor_position=0)

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptAdjustEmphasisContentAction(
                content_start=0,
                content_end=3,
                delta=Decimal("0.05"),
            ),
            source_identity=_source_identity(session),
            cursor_policy="preserve_cursor",
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "(cat:1.05)"
    assert result.mutation is not None
    assert result.mutation.selection_start == 1
    assert result.mutation.selection_end == 4
    assert result.render_plan is not None
    assert result.cursor_state == PromptCursorState(
        cursor_position=3,
        anchor_position=0,
    )
    assert session.can_undo()


def test_exact_neutral_emphasis_command_preserves_cursor_without_source_change() -> (
    None
):
    """Exact neutral emphasis should expose the mutation even when source is unchanged."""

    session = _session("cat", cursor_position=2)

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptSetEmphasisWeightContentAction(
                content_start=0,
                content_end=3,
                weight=Decimal("1.00"),
            ),
            cursor_policy="preserve_cursor",
        ),
    )

    assert result.status == "noop"
    assert result.reason == "same_source"
    assert session.source_text == "cat"
    assert result.mutation is not None
    assert result.mutation.selection_start == 0
    assert result.mutation.selection_end == 3
    assert result.render_plan is not None


def test_stale_weight_identity_rejects_without_mutation() -> None:
    """Weight commands should fail closed when prepared source identity changed."""

    session = _session("(cat:1.05)")

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptSetEmphasisWeightAction(
                outer_start=0,
                outer_end=10,
                weight=Decimal("1.20"),
            ),
            source_identity=PromptCommandSourceIdentity(
                source_revision=session.source_revision + 1,
                source_length=len(session.source_text),
            ),
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == "(cat:1.05)"
    assert not session.can_undo()


def test_stale_outer_range_rejects_without_mutation() -> None:
    """Outer-range weight actions should reject when the syntax target disappeared."""

    session = _session("cat")

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptSetEmphasisWeightAction(
                outer_start=0,
                outer_end=10,
                weight=Decimal("1.20"),
            ),
        ),
    )

    assert result.status == "rejected"
    assert result.reason == "stale_or_invalid_weight_action"
    assert session.source_text == "cat"
    assert not session.can_undo()


def test_after_mutation_cursor_policy_places_caret_after_emphasis_shell() -> None:
    """Exact weight commits can place the caret after the updated syntax object."""

    session = _session("(test:1)", cursor_position=len("test"))

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptSetEmphasisWeightAction(
                outer_start=0,
                outer_end=len("(test:1)"),
                weight=Decimal("1.20"),
            ),
            cursor_policy="after_mutation",
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "(test:1.20)"
    assert result.cursor_state == PromptCursorState(
        cursor_position=len("(test:1.20)"),
        anchor_position=len("(test:1.20)"),
    )


def test_lora_weight_commands_adjust_and_set_first_weight() -> None:
    """LoRA weight commands should mutate only the first schedule weight."""

    adjust_session = _session("<lora:midna:1.00>")
    adjust_result = _execute_weight_request(
        adjust_session,
        PromptWeightActionRequest(
            action=PromptAdjustLoraWeightAction(
                outer_start=0,
                outer_end=len("<lora:midna:1.00>"),
                delta=Decimal("0.05"),
            ),
        ),
    )
    set_session = _session("<lora:midna:1.00:0.50>")
    set_result = _execute_weight_request(
        set_session,
        PromptWeightActionRequest(
            action=PromptSetLoraWeightAction(
                outer_start=0,
                outer_end=len("<lora:midna:1.00:0.50>"),
                weight=Decimal("0.75"),
            ),
        ),
    )

    assert adjust_result.status == "applied"
    assert adjust_session.source_text == "<lora:midna:1.05>"
    assert set_result.status == "applied"
    assert set_session.source_text == "<lora:midna:0.75:0.50>"


def test_numeric_wildcard_command_persists_adjusted_tag() -> None:
    """Numeric wildcard commands should persist stepped display tags."""

    session = _session("{animal}")

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptAdjustWildcardTagAction(
                outer_start=0,
                outer_end=len("{animal}"),
                current_display_tag="1",
                delta=1,
            ),
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "{animal|2}"
    assert result.mutation is not None
    assert result.mutation.selection_start == len("{animal|2}") - 1
    assert result.mutation.selection_end == len("{animal|2}") - 1


def test_wildcard_set_tag_command_persists_exact_tag() -> None:
    """Exact wildcard tag commands should persist through the command path."""

    session = _session("{animal|1}")

    result = _execute_weight_request(
        session,
        PromptWeightActionRequest(
            action=PromptSetWildcardTagAction(
                outer_start=0,
                outer_end=len("{animal|1}"),
                tag="night",
            ),
        ),
    )

    assert result.status == "applied"
    assert session.source_text == "{animal|night}"
    assert result.mutation is not None
    assert result.mutation.selection_start == len("{animal|night}") - 1
    assert result.mutation.selection_end == len("{animal|night}") - 1
