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

"""Verify atomic runtime registration for canvas modes and workflow actions."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QIcon
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.tools import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolRuntime,
)


def _contribution(
    tool_id: str,
    kind: CanvasToolKind,
) -> CanvasToolContribution:
    """Create one unconstrained runtime contribution."""

    return CanvasToolContribution(
        tool_id=tool_id,
        label=app_text(tool_id),
        icon=QIcon(),
        kind=kind,
        section="runtime",
        order=100,
    )


def test_runtime_pairs_actions_with_handlers_and_cleans_both_owners() -> None:
    """Action visibility, dispatch, and removal should share one lifecycle."""

    runtime = CanvasToolRuntime()
    calls: list[str] = []

    def execute() -> bool:
        """Record one successful workflow action."""

        calls.append("ran")
        return True

    runtime.register_action(
        _contribution("workflow.remove-background", CanvasToolKind.ACTION),
        execute,
    )

    assert runtime.dispatch_action("workflow.remove-background") is True
    assert calls == ["ran"]
    assert runtime.unregister("workflow.remove-background") is True
    assert runtime.dispatch_action("workflow.remove-background") is False
    assert runtime.registry.contribution("workflow.remove-background") is None


def test_runtime_rejects_mismatched_and_duplicate_registration_atomically() -> None:
    """Invalid registration must not leave an orphan contribution or handler."""

    runtime = CanvasToolRuntime()
    action = _contribution("workflow.action", CanvasToolKind.ACTION)
    mode = _contribution("editor.mode", CanvasToolKind.MODE)

    with pytest.raises(ValueError, match="mode contribution"):
        runtime.register_mode(action)
    with pytest.raises(ValueError, match="action contribution"):
        runtime.register_action(mode, lambda: True)

    runtime.register_action(action, lambda: True)
    with pytest.raises(ValueError, match="already registered"):
        runtime.register_action(action, lambda: True)
    assert runtime.dispatch_action(action.tool_id) is True


def test_runtime_action_failure_is_contained_and_runtime_remains_usable() -> None:
    """A hostile user action must not escape into the Qt event callback."""

    runtime = CanvasToolRuntime()

    def fail() -> bool:
        """Raise one hostile extension failure."""

        raise RuntimeError("extension failed")

    runtime.register_action(
        _contribution("workflow.failing", CanvasToolKind.ACTION),
        fail,
    )
    runtime.register_action(
        _contribution("workflow.healthy", CanvasToolKind.ACTION),
        lambda: True,
    )

    assert runtime.dispatch_action("workflow.failing") is False
    assert runtime.dispatch_action("workflow.healthy") is True
