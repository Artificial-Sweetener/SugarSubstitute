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

"""Define source-backed weight commands for prompt editing."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar, cast

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
    PromptAdjustEmphasisContentAction,
    PromptAdjustLoraWeightAction,
    PromptAdjustWildcardTagAction,
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
    PromptSetLoraWeightAction,
    PromptSetWildcardTagAction,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from ..core.editing.commands import PromptReplaceDocumentEdit
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import PromptSourceNormalizer
from ..core.editing.transactions import PromptUndoSnapshot
from substitute.shared.logging.logger import get_logger, log_warning_exception

from .contracts import PromptCommandResult, PromptEditApplicationState
from .execution import PromptEditExecution

TPayload = TypeVar("TPayload")

_LOGGER = get_logger("presentation.editor.prompt_editor.commands.weight_commands")

PromptSyntaxWeightAction: TypeAlias = (
    PromptAdjustEmphasisAction
    | PromptAdjustEmphasisContentAction
    | PromptSetEmphasisWeightAction
    | PromptSetEmphasisWeightContentAction
    | PromptAdjustLoraWeightAction
    | PromptSetLoraWeightAction
    | PromptSetWildcardTagAction
    | PromptAdjustWildcardTagAction
)
PromptWeightCursorPolicy = Literal[
    "preserve_cursor",
    "mutation_selection",
    "after_mutation",
]


@dataclass(frozen=True, slots=True)
class PromptWeightActionRequest:
    """Describe one prepared prompt weight mutation request."""

    action: PromptSyntaxWeightAction
    source_identity: PromptSourceIdentity | None = None
    cursor_policy: PromptWeightCursorPolicy = "mutation_selection"


@dataclass(frozen=True, slots=True)
class PromptWeightCommandResult(PromptCommandResult[TPayload]):
    """Report a weight command mutation and optional prepared render plan."""

    mutation: PromptMutation | None = None
    render_plan: PromptSyntaxRenderPlan | None = None


class PromptWeightCommandService(Generic[TPayload]):
    """Execute weight mutations through one grouped editing transaction."""

    def __init__(
        self,
        *,
        execution: PromptEditExecution[TPayload],
        normalizer: PromptSourceNormalizer,
        exact_source_enabled: Callable[[], bool],
    ) -> None:
        """Store weight command dependencies."""

        self._execution = execution
        self._normalizer = normalizer
        self._exact_source_enabled = exact_source_enabled

    def execute(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[TPayload]:
        """Commit one prepared weight mutation."""

        command = build_weight_action_command(
            request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            normalizer=self._normalizer,
            exact_source=self._exact_source_enabled(),
            record_undo=False,
            undo_snapshot=self._execution.current_undo_snapshot(),
        )
        self._execution.finish_pending_key_edit_block(reason="weight_action")
        self._execution.begin_edit_block(finish_typing=False)
        try:
            return cast(
                PromptWeightCommandResult[TPayload],
                self._execution.execute(command),
            )
        finally:
            self._execution.end_edit_block()


@dataclass(frozen=True, slots=True)
class PromptApplySyntaxWeightCommand(Generic[TPayload]):
    """Apply one syntax weight request through the editing session."""

    request: PromptWeightActionRequest
    mutation_service: PromptMutationService
    syntax_service: PromptSyntaxService
    syntax_profile: PromptSyntaxProfile
    normalizer: PromptSourceNormalizer
    exact_source: bool
    record_undo: bool
    undo_snapshot: PromptUndoSnapshot[TPayload]
    name: str = "apply_syntax_weight"

    def execute(
        self,
        session: PromptEditingSession[TPayload],
    ) -> PromptWeightCommandResult[TPayload]:
        """Apply this weight request through the supplied session."""

        stale_result = _stale_result(
            command_name=self.name,
            session=session,
            source_identity=self.request.source_identity,
        )
        if stale_result is not None:
            return stale_result

        mutation = self.mutation_service.apply_syntax_action(
            session.source_text,
            self.request.action,
        )
        if mutation is None:
            return _rejected(self.name, "stale_or_invalid_weight_action")

        render_plan = _render_plan_for_mutation(
            syntax_service=self.syntax_service,
            syntax_profile=self.syntax_profile,
            mutation=mutation,
        )
        cursor_position, anchor_position = _cursor_output_for_mutation(
            session=session,
            mutation=mutation,
            action=self.request.action,
            cursor_policy=self.request.cursor_policy,
        )
        edit_commit = session.execute(
            PromptReplaceDocumentEdit(
                text=mutation.text,
                cursor_position=cursor_position,
                anchor_position=anchor_position,
                normalizer=self.normalizer,
                exact_source=self.exact_source,
                record_undo=self.record_undo,
                clear_history=False,
                undo_snapshot=self.undo_snapshot,
            )
        )
        edit_commit = edit_commit.with_prepared_state(
            PromptEditApplicationState(
                document_view=mutation.document_view,
                render_plan=render_plan,
            )
        )
        return PromptWeightCommandResult(
            command_name=self.name,
            status="applied" if edit_commit.source_changed else "noop",
            edit_commit=edit_commit,
            cursor_state=edit_commit.cursor_state,
            undo_availability_change=edit_commit.undo_availability_change,
            reason=None if edit_commit.source_changed else "same_source",
            mutation=mutation,
            render_plan=render_plan,
        )


def build_weight_action_command(
    request: PromptWeightActionRequest,
    *,
    mutation_service: PromptMutationService,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
    normalizer: PromptSourceNormalizer,
    exact_source: bool,
    record_undo: bool,
    undo_snapshot: PromptUndoSnapshot[TPayload],
) -> PromptApplySyntaxWeightCommand[TPayload]:
    """Return the executable command for one prepared weight action."""

    return PromptApplySyntaxWeightCommand(
        request=request,
        mutation_service=mutation_service,
        syntax_service=syntax_service,
        syntax_profile=syntax_profile,
        normalizer=normalizer,
        exact_source=exact_source,
        record_undo=record_undo,
        undo_snapshot=undo_snapshot,
    )


def _cursor_output_for_mutation(
    *,
    session: PromptEditingSession[TPayload],
    mutation: PromptMutation,
    action: PromptSyntaxWeightAction,
    cursor_policy: PromptWeightCursorPolicy,
) -> tuple[int, int]:
    """Return the command cursor output for one weight mutation."""

    source_length = len(mutation.text)
    if cursor_policy == "after_mutation":
        cursor_position = _after_mutation_cursor_position(
            mutation,
            action=action,
        )
        if cursor_position is not None:
            bounded_position = max(0, min(cursor_position, source_length))
            return bounded_position, bounded_position
    if (
        cursor_policy == "mutation_selection"
        and mutation.selection_start is not None
        and mutation.selection_end is not None
    ):
        return (
            max(0, min(mutation.selection_end, source_length)),
            max(0, min(mutation.selection_start, source_length)),
        )
    return (
        max(0, min(session.cursor_position, source_length)),
        max(0, min(session.anchor_position, source_length)),
    )


def _after_mutation_cursor_position(
    mutation: PromptMutation,
    *,
    action: PromptSyntaxWeightAction,
) -> int | None:
    """Return the source boundary after the syntax object changed by one action."""

    document_view = mutation.document_view
    if isinstance(
        action,
        (
            PromptAdjustEmphasisAction,
            PromptSetEmphasisWeightAction,
        ),
    ):
        for emphasis_span in document_view.emphasis_spans:
            if emphasis_span.outer_start == action.outer_start:
                return emphasis_span.outer_end
        return mutation.selection_end
    if isinstance(
        action,
        (
            PromptAdjustEmphasisContentAction,
            PromptSetEmphasisWeightContentAction,
        ),
    ):
        for emphasis_span in document_view.emphasis_spans:
            if (
                emphasis_span.content_start == action.content_start
                and emphasis_span.content_end == action.content_end
            ):
                return emphasis_span.outer_end
        return mutation.selection_end
    if isinstance(
        action,
        (
            PromptAdjustLoraWeightAction,
            PromptSetLoraWeightAction,
        ),
    ):
        for lora_span in document_view.lora_spans:
            if lora_span.outer_start == action.outer_start:
                return lora_span.outer_end
        return mutation.selection_end
    if isinstance(
        action,
        (
            PromptAdjustWildcardTagAction,
            PromptSetWildcardTagAction,
        ),
    ):
        for wildcard_span in document_view.wildcard_spans:
            if wildcard_span.outer_start == action.outer_start:
                return wildcard_span.outer_end
        return mutation.selection_end
    return mutation.selection_end


def _render_plan_for_mutation(
    *,
    syntax_service: PromptSyntaxService,
    syntax_profile: PromptSyntaxProfile,
    mutation: PromptMutation,
) -> PromptSyntaxRenderPlan | None:
    """Build a render plan for immediate prompt-state adoption when possible."""

    try:
        return syntax_service.build_render_plan(
            mutation.document_view,
            syntax_profile,
        )
    except Exception as error:
        log_warning_exception(
            _LOGGER,
            "Prompt syntax render-plan refresh failed",
            error=error,
            source_length=len(mutation.document_view.source_text),
        )
        return None


def _stale_result(
    *,
    command_name: str,
    session: PromptEditingSession[TPayload],
    source_identity: PromptSourceIdentity | None,
) -> PromptWeightCommandResult[TPayload] | None:
    """Return a stale rejection for a mismatched prepared source identity."""

    if source_identity is None:
        return None
    if source_identity.matches(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    ):
        return None
    return _rejected(command_name, "stale_source")


def _rejected(
    command_name: str,
    reason: str,
) -> PromptWeightCommandResult[TPayload]:
    """Build a typed weight command rejection."""

    return PromptWeightCommandResult(
        command_name=command_name,
        status="rejected",
        reason=reason,
    )


__all__ = [
    "PromptApplySyntaxWeightCommand",
    "PromptSyntaxWeightAction",
    "PromptWeightActionRequest",
    "PromptWeightCommandService",
    "PromptWeightCommandResult",
    "PromptWeightCursorPolicy",
    "build_weight_action_command",
]
