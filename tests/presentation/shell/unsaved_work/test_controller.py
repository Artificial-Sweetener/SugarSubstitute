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

"""Verify Save, Don't Save, and Cancel orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.workflows.unsaved_work_service import (
    UnsavedWorkDecision,
    UnsavedWorkService,
)
from substitute.presentation.shell.unsaved_work_controller import UnsavedWorkController


class _Prompt:
    """Return scripted user decisions without showing a window."""

    def __init__(self, decisions: list[UnsavedWorkDecision]) -> None:
        """Store decisions and captured labels."""

        self.decisions = decisions
        self.labels: list[str] = []

    def decide(self, *, parent: object, workflow_name: str) -> UnsavedWorkDecision:
        """Return the next scripted decision."""

        del parent
        self.labels.append(workflow_name)
        return self.decisions.pop(0)


class _TabBar:
    """Expose ordered workflow tabs."""

    def __init__(self) -> None:
        """Create two labeled tabs."""

        self.itemMap = {
            "one": SimpleNamespace(text=lambda: "One"),
            "two": SimpleNamespace(text=lambda: "Two"),
        }

    def workflow_ids_in_order(self) -> list[str]:
        """Return stable visible ordering."""

        return ["one", "two"]


def _shell(*, save_result: bool = True) -> SimpleNamespace:
    """Build a narrow shell double for dirty-work decisions."""

    service = UnsavedWorkService()
    service.mark_dirty("one")
    service.mark_dirty("two")
    activations: list[str] = []
    saves: list[str] = []
    session = SimpleNamespace(active_workflow_id="one")

    def activate(workflow_id: str, *, source: str) -> None:
        """Record active-workflow projection."""

        assert source == "unsaved_work_save"
        session.active_workflow_id = workflow_id
        activations.append(workflow_id)

    def save() -> bool:
        """Record one explicit save result."""

        saves.append(session.active_workflow_id)
        return save_result

    return SimpleNamespace(
        unsaved_work_service=service,
        workflow_tabbar=_TabBar(),
        workflow_session_service=session,
        workflow_workspace=SimpleNamespace(activate_workflow=activate),
        workspace_file_actions=SimpleNamespace(on_save_clicked=save),
        activations=activations,
        saves=saves,
    )


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (UnsavedWorkDecision.DISCARD, True),
        (UnsavedWorkDecision.CANCEL, False),
    ],
)
def test_close_applies_non_save_decisions(
    decision: UnsavedWorkDecision,
    expected: bool,
) -> None:
    """Discard should continue while Cancel must stop closure."""

    shell = _shell()
    prompt = _Prompt([decision])
    controller = UnsavedWorkController(shell, prompt=cast(Any, prompt))

    assert controller.confirm_workflow_close("one") is expected
    assert prompt.labels == ["One"]
    assert shell.saves == []


def test_save_activates_target_and_blocks_when_persistence_fails() -> None:
    """A failed explicit save must fail closed at a destructive boundary."""

    shell = _shell(save_result=False)
    prompt = _Prompt([UnsavedWorkDecision.SAVE])
    controller = UnsavedWorkController(shell, prompt=cast(Any, prompt))

    assert controller.confirm_workflow_close("two") is False
    assert shell.activations == ["two"]
    assert shell.saves == ["two"]


def test_shutdown_stops_at_cancel_without_losing_remaining_documents() -> None:
    """Cancel should abort shutdown immediately and preserve remaining work."""

    shell = _shell()
    prompt = _Prompt([UnsavedWorkDecision.DISCARD, UnsavedWorkDecision.CANCEL])
    controller = UnsavedWorkController(shell, prompt=cast(Any, prompt))

    assert controller.confirm_shutdown() is False
    assert prompt.labels == ["One", "Two"]
