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
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.tools import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolProviderSnapshot,
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


class _Provider:
    """Return one declarative runtime extension snapshot."""

    def __init__(self, snapshot: CanvasToolProviderSnapshot) -> None:
        """Store one immutable provider snapshot."""

        self._snapshot = snapshot

    def canvas_tool_snapshot(self) -> CanvasToolProviderSnapshot:
        """Return the configured snapshot."""

        return self._snapshot


def test_provider_boundary_installs_metadata_and_options_atomically() -> None:
    """Hostile provider metadata must never leave partially installed tools."""

    app = QCoreApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    runtime = CanvasToolRuntime()
    mode = CanvasToolContribution(
        tool_id="extension.mode",
        label=app_text("Extension mode"),
        icon=QIcon(),
        kind=CanvasToolKind.MODE,
        section="extension",
        order=900,
        document_operation_id="native.extension",
        options_id="extension.options",
        preview_id="extension.preview",
    )
    invalid = _Provider(
        CanvasToolProviderSnapshot(
            contributions=(mode,),
            actions={"extension.mode": lambda: True},
        )
    )
    with pytest.raises(ValueError, match="action metadata"):
        runtime.install_provider(invalid)
    assert runtime.registry.snapshot() == ()

    runtime.install_provider(
        _Provider(
            CanvasToolProviderSnapshot(
                contributions=(mode,),
                options={"extension.options": lambda parent: QWidget(parent)},
            )
        )
    )
    parent = QWidget()
    options = runtime.create_options_widget("extension.options", parent)
    assert options is not None and options.parentWidget() is parent
    contribution = runtime.registry.contribution("extension.mode")
    assert contribution is not None
    assert contribution.document_operation_id == "native.extension"
    assert contribution.preview_id == "extension.preview"
