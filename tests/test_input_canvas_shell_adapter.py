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

"""Tests for shell adapters used by Input canvas collaborators."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.input_canvas_shell_adapter import (
    InputCanvasShellAdapter,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CANVAS_AND_GENERATION_SURFACES,
    WorkflowInvalidationReason,
)


class _TabItem:
    """Minimal workflow tab item exposing text."""

    def __init__(self, text: str) -> None:
        """Store the displayed tab text."""

        self._text = text

    def text(self) -> str:
        """Return the displayed tab text."""

        return self._text


def test_resolve_workflow_name_uses_trimmed_tab_label() -> None:
    """Workflow names should come from the current workflow tab text."""

    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(itemMap={"wf-a": _TabItem("  Recipe A  ")})
    )

    assert InputCanvasShellAdapter(shell).resolve_workflow_name("wf-a") == "Recipe A"


def test_resolve_workflow_name_falls_back_when_tab_missing_or_blank() -> None:
    """Missing and blank workflow tabs should use the stable untitled fallback."""

    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(itemMap={"wf-a": _TabItem("   ")})
    )
    adapter = InputCanvasShellAdapter(shell)

    assert adapter.resolve_workflow_name("wf-a") == "untitled_workflow"
    assert adapter.resolve_workflow_name("wf-missing") == "untitled_workflow"


def test_mark_input_canvas_changed_marks_canvas_and_generation_surfaces() -> None:
    """Input canvas mutations should dirty all surfaces affected by canvas state."""

    calls: list[tuple[str, object, object]] = []
    shell = SimpleNamespace(
        workflow_surface_invalidation_service=SimpleNamespace(
            mark_dirty=lambda workflow_id, surfaces, reason: calls.append(
                (workflow_id, surfaces, reason)
            )
        )
    )

    InputCanvasShellAdapter(shell).mark_input_canvas_changed("wf-a")

    assert calls == [
        (
            "wf-a",
            CANVAS_AND_GENERATION_SURFACES,
            WorkflowInvalidationReason.CANVAS_STATE_CHANGED,
        )
    ]
