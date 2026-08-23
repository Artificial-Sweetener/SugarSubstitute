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

"""Replay and minimize recorded real-shell prompt editor interactions."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt

from tests.support.prompt_editor.real_shell.input_driver import PromptEditorInputDriver
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorTrace,
    PromptEditorTraceAction,
    PromptFieldHandle,
    PromptWorkflowHandle,
)
from tests.support.prompt_editor.real_shell.workflows import PromptWorkflowMounts


class PromptEditorTraceReplay:
    """Own recorded interaction replay against one mounted real-shell scenario."""

    def __init__(
        self,
        *,
        actions: list[PromptEditorTraceAction],
        input_driver: PromptEditorInputDriver,
        workflow_handles: dict[str, PromptWorkflowHandle],
        workflows: PromptWorkflowMounts,
    ) -> None:
        """Bind replay to the collaborators that own each real interaction."""

        self._actions = actions
        self._input = input_driver
        self._workflow_handles = workflow_handles
        self._workflows = workflows

    def trace(self) -> PromptEditorTrace:
        """Return the recorded interaction trace."""

        return PromptEditorTrace(actions=tuple(self._actions))

    def replay(self, field: PromptFieldHandle, trace: PromptEditorTrace) -> None:
        """Replay actions through their production input and workflow owners."""

        for action in trace.actions:
            if action.kind == "type_text":
                self._input.type_text(field, action.value)
            elif action.kind == "paste_text":
                self._input.paste_text(field, action.value)
            elif action.kind == "undo":
                self._input.undo(field)
            elif action.kind == "redo":
                self._input.redo(field)
            elif action.kind == "replace_text":
                self._input.replace_text_with_keys(field, action.value)
            elif action.kind == "press_key" and action.key is not None:
                self._input.press_key(
                    field,
                    Qt.Key(action.key),
                    text=action.value,
                    modifiers=Qt.KeyboardModifier(action.modifiers),
                )
            elif action.kind == "click_away":
                self._input.click_away_from_editor()
            elif action.kind == "switch_canvas":
                self._input.switch_canvas(action.value)
            elif action.kind == "activate_workflow":
                self._activate_workflow(action.value)
            elif action.kind == "scroll_editor":
                self._input.scroll_editor(field, action.value)
            elif action.kind == "seed_text_directly":
                self._input.seed_text_directly(field, action.value)
            else:
                raise AssertionError(f"unknown trace action {action!r}")

    def minimize(
        self,
        trace: PromptEditorTrace,
        predicate: Callable[[PromptEditorTrace], bool],
    ) -> PromptEditorTrace:
        """Remove actions while preserving the caller's visible failure predicate."""

        actions = list(trace.actions)
        index = 0
        while index < len(actions):
            candidate = PromptEditorTrace(
                tuple(actions[:index] + actions[index + 1 :]),
                seed=trace.seed,
            )
            if predicate(candidate):
                actions = list(candidate.actions)
                continue
            index += 1
        return PromptEditorTrace(tuple(actions), seed=trace.seed)

    def _activate_workflow(self, alias: str) -> None:
        """Ensure the traced workflow exists before activating it."""

        if alias not in self._workflow_handles:
            self._workflows.add_prompt_workflow(
                alias,
                initial_text="secondary prompt",
                activate=False,
            )
        self._workflows.activate_workflow(alias)
