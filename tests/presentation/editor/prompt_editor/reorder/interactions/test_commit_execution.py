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

"""Verify prompt reorder commit execution contracts."""

from __future__ import annotations

from typing import cast


from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_commit_execution import (
    PromptReorderCommitExecutor,
)
from substitute.presentation.editor.prompt_editor.commands.reorder_commands import (
    PromptReorderCommandResult,
)


def _layout(*indices: int) -> PromptReorderLayoutView:
    """Build one single-row reorder layout for owner tests."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=indices),),
        gaps=(),
    )


def _state(*indices: int) -> PromptReorderStateView:
    """Build one same-row reorder state for commit execution."""

    return PromptReorderStateView(
        ordered_chip_indices=indices,
        separator_slots=tuple(", " for _ in indices[:-1]),
        has_trailing_comma=False,
    )


def test_reorder_commit_executor_invokes_and_publishes_one_prepared_request() -> None:
    """Command execution owns one narrow call followed by one result publication."""

    class _Surface:
        def __init__(self) -> None:
            self.requests: list[object] = []

        def execute_reorder_action(
            self,
            request: PromptReorderLayoutCommitRequest,
            *,
            mutation_service: PromptMutationService,
            syntax_service: PromptSyntaxService,
            syntax_profile: PromptSyntaxProfile,
        ) -> PromptReorderCommandResult[object]:
            _ = mutation_service, syntax_service, syntax_profile
            self.requests.append(request)
            return PromptReorderCommandResult(command_name="reorder", status="applied")

        def toPlainText(self) -> str:  # noqa: N802
            return "alpha"

    class _ResultPort:
        def __init__(self) -> None:
            self.results: list[object] = []

        def apply_reorder_result(
            self, result: PromptReorderCommandResult[object]
        ) -> None:
            self.results.append(result)

    surface = _Surface()
    result_port = _ResultPort()
    request = PromptReorderLayoutCommitRequest(
        reorder_state=_state(0, 1), layout_view=_layout(0, 1), selected_chip_index=0
    )
    executor = PromptReorderCommitExecutor(
        surface,
        result_port=result_port,
        mutation_service=cast(PromptMutationService, object()),
        syntax_service=cast(PromptSyntaxService, object()),
        syntax_profile=cast(PromptSyntaxProfile, object()),
    )

    executor.execute(request, reason="owner_test")

    assert surface.requests == [request]
    assert len(result_port.results) == 1
