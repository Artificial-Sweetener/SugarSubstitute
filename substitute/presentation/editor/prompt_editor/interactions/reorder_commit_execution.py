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

"""Execute prepared reorder commands outside overlay-session lifecycle ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)

from ..commands.reorder_commands import PromptReorderCommandResult
from ..projection.observability import log_reorder_drag_timing, reorder_drag_started_at


class PromptReorderCommandSurface(Protocol):
    """Expose only source-command execution and text observation for reorder commits."""

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared prompt reorder action through commands."""

    def toPlainText(self) -> str:
        """Return current source text for observability fallback only."""


class PromptReorderCommandResultPort(Protocol):
    """Adopt the authoritative result of one committed reorder command."""

    def apply_reorder_result(self, result: PromptReorderCommandResult[object]) -> None:
        """Publish a successful command result into prompt-editor state."""


@dataclass(frozen=True, slots=True)
class PromptReorderCommitExecution:
    """Carry measured command and result-publication durations for one commit."""

    command_elapsed_ms: float
    apply_elapsed_ms: float


class PromptReorderCommitExecutor:
    """Own command invocation, result adoption, and bounded commit timing records."""

    def __init__(
        self,
        surface: PromptReorderCommandSurface,
        *,
        result_port: PromptReorderCommandResultPort,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> None:
        """Store the narrow command ports and immutable command collaborators."""

        self._surface = surface
        self._result_port = result_port
        self._mutation_service = mutation_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile

    def execute(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        reason: str,
    ) -> PromptReorderCommitExecution:
        """Execute and publish one already-approved reorder request."""

        started_at = reorder_drag_started_at()
        result = self._surface.execute_reorder_action(
            request,
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
        )
        command_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.command",
            started_at=started_at,
            active_chip_index=request.selected_chip_index,
            intent_reason=reason,
            row_count=0
            if request.layout_view is None
            else len(request.layout_view.rows),
            gap_count=0
            if request.layout_view is None
            else len(request.layout_view.gaps),
            text_length=(
                len(result.mutation.text)
                if result.mutation is not None
                else len(self._surface.toPlainText())
            ),
        )
        started_at = reorder_drag_started_at()
        self._result_port.apply_reorder_result(result)
        apply_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.apply_command_result",
            started_at=started_at,
            intent_reason=reason,
        )
        return PromptReorderCommitExecution(
            command_elapsed_ms=command_elapsed_ms,
            apply_elapsed_ms=apply_elapsed_ms,
        )


__all__ = ["PromptReorderCommitExecution", "PromptReorderCommitExecutor"]
