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

"""Expose the prompt editor's prepared command execution boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

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

from .commands.autocomplete_commands import PromptAutocompleteAcceptance
from .commands.contracts import PromptCommandResult, PromptCommandTextReplacement
from .commands.diagnostic_commands import (
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
)
from .commands.reorder_commands import (
    PromptReorderCommandResult,
)
from .commands.weight_commands import (
    PromptWeightActionRequest,
    PromptWeightCommandResult,
)
from .core.state.revisions import PromptSourceIdentity

if TYPE_CHECKING:
    from .runtime_mount import PromptEditorRuntimeMount


class PromptEditorCommandFacade:
    """Route public prepared commands to their focused execution services."""

    _runtime: PromptEditorRuntimeMount

    def prompt_command_source_identity(self) -> PromptSourceIdentity:
        """Return the current source identity for prepared prompt commands."""

        return self._runtime.projection.source_commands.source_identity()

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Execute one prepared autocomplete acceptance."""

        return cast(
            PromptCommandResult[object],
            self._runtime.projection.autocomplete_commands.execute(acceptance),
        )

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one prepared diagnostic action."""

        return cast(
            PromptDiagnosticCommandResult[object],
            self._runtime.projection.diagnostic_commands.execute(action),
        )

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute one prepared prompt-weight action."""

        return cast(
            PromptWeightCommandResult[object],
            self._runtime.projection.weight_commands.execute(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared reorder commit."""

        return cast(
            PromptReorderCommandResult[object],
            self._runtime.projection.reorder_commands.execute(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[object]:
        """Execute one prepared source replacement."""

        return cast(
            PromptCommandResult[object],
            self._runtime.projection.source_commands.execute_source_replacement(
                replacement,
                command_name=command_name,
            ),
        )


__all__ = ["PromptEditorCommandFacade"]
