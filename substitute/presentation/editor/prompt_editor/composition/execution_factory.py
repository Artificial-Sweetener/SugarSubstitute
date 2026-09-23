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

"""Own prompt-editor asynchronous execution adapter construction."""

from __future__ import annotations

from itertools import count

from ..async_work import PromptEditorTaskExecutor, PromptLatestWinsRequestChannel
from .collaborator_bundle import PromptEditorConstructionInputs
from .context import PromptEditorCompositionContext


class PromptEditorExecutionFactory:
    """Create uniquely identified task executors and latest-wins channels."""

    _request_ids = count(1)

    def __init__(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
    ) -> None:
        """Retain the construction boundary shared by all async collaborators."""
        self._inputs = inputs
        self._context = context

    def build_task_executor(self, *, owner_label: str) -> PromptEditorTaskExecutor:
        """Build one uniquely identified prompt task executor."""
        executor_factory = self._inputs.prompt_task_executor_factory
        if executor_factory is None:
            raise RuntimeError("prompt_task_executor_factory is required.")
        request_id = next(self._request_ids)
        editor = self._context.editor
        return executor_factory(
            editor,
            f"{owner_label}:{id(editor):x}:{request_id}",
        )

    def build_request_channel(
        self,
        *,
        owner_label: str,
    ) -> PromptLatestWinsRequestChannel[object]:
        """Build one latest-wins request channel on a dedicated executor."""
        return PromptLatestWinsRequestChannel(
            executor=self.build_task_executor(owner_label=owner_label)
        )
