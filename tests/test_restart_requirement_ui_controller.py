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

"""Tests for the pending restart presentation controller."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtWidgets import QApplication, QDialog
import pytest

from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.presentation.restart_requirements import RestartRequirementUiController
from substitute.presentation.shell.pending_restart_toolbar_button import (
    PendingRestartToolbarButton,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "restart UI Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


class _Dialog:
    """Fake restart dialog that records execution and returns a fixed result."""

    def __init__(self, result: int) -> None:
        """Store the dialog result returned from exec."""

        self.result = result
        self.exec_count = 0

    def exec(self) -> int:
        """Record execution and return the configured result."""

        self.exec_count += 1
        return self.result


def _app() -> QApplication:
    """Return the shared QApplication used by controller tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_restart_ui_controller_updates_button_from_service() -> None:
    """Controller should mirror service snapshots into the restart button."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: None,
        restart_window=lambda: None,
        parent=None,
    )

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )

    assert button.count() == 1
    assert button.is_collapsed() is False

    service.clear("comfy.model_root")

    assert button.count() == 0
    assert button.is_collapsed() is True

    controller.dispose()
    button.close()


def test_restart_ui_controller_runs_restart_callback_on_accept() -> None:
    """Accepting the dialog should invoke the full-app restart callback."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    dialog = _Dialog(int(QDialog.DialogCode.Accepted))
    restart_calls: list[str] = []
    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: restart_calls.append("restart"),
        restart_window=lambda: restart_calls.append("window"),
        parent=None,
        dialog_factory=lambda _snapshot, _parent: dialog,
    )

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    controller.show_restart_required_dialog()

    assert dialog.exec_count == 1
    assert restart_calls == ["restart"]

    controller.dispose()
    button.close()


def test_restart_ui_controller_later_keeps_pending_without_restart() -> None:
    """Rejecting the dialog should not clear items or restart the app."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    dialog = _Dialog(int(QDialog.DialogCode.Rejected))
    restart_calls: list[str] = []
    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: restart_calls.append("restart"),
        restart_window=lambda: restart_calls.append("window"),
        parent=None,
        dialog_factory=lambda _snapshot, _parent: dialog,
    )

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    controller.show_restart_required_dialog()

    assert dialog.exec_count == 1
    assert restart_calls == []
    assert service.snapshot().count == 1
    assert button.is_collapsed() is False

    controller.dispose()
    button.close()


def test_restart_ui_controller_runs_window_callback_for_window_scope() -> None:
    """Accepting a window-scoped dialog should invoke the GUI reload callback."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    dialog = _Dialog(int(QDialog.DialogCode.Accepted))
    restart_calls: list[str] = []
    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: restart_calls.append("full"),
        restart_window=lambda: restart_calls.append("window"),
        parent=None,
        dialog_factory=lambda _snapshot, _parent: dialog,
    )

    service.register_delta(
        key="appearance.theme_mode",
        label="Theme mode",
        active_value="dark",
        saved_value="light",
        scope=RestartScope.WINDOW,
    )
    controller.show_restart_required_dialog()

    assert dialog.exec_count == 1
    assert restart_calls == ["window"]

    controller.dispose()
    button.close()


def test_restart_ui_controller_prefers_full_app_for_mixed_scopes() -> None:
    """Accepting mixed pending work should run the most expensive restart."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    dialog = _Dialog(int(QDialog.DialogCode.Accepted))
    restart_calls: list[str] = []
    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: restart_calls.append("full"),
        restart_window=lambda: restart_calls.append("window"),
        parent=None,
        dialog_factory=lambda _snapshot, _parent: dialog,
    )

    service.register_delta(
        key="appearance.theme_mode",
        label="Theme mode",
        active_value="dark",
        saved_value="light",
        scope=RestartScope.WINDOW,
    )
    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    controller.show_restart_required_dialog()

    assert restart_calls == ["full"]

    controller.dispose()
    button.close()


def test_restart_ui_controller_ignores_empty_snapshot_dialog_requests() -> None:
    """Controller should not open a dialog when no restart items are pending."""

    _app()
    service = RestartRequirementService()
    button = PendingRestartToolbarButton()
    dialog_calls: list[RestartRequirementSnapshot] = []

    def create_dialog(
        snapshot: RestartRequirementSnapshot,
        _parent: object,
    ) -> _Dialog:
        """Record the requested snapshot and return an accepted fake dialog."""

        dialog_calls.append(snapshot)
        return _Dialog(int(QDialog.DialogCode.Accepted))

    controller = RestartRequirementUiController(
        service=service,
        button=button,
        restart_full_app=lambda: None,
        restart_window=lambda: None,
        parent=None,
        dialog_factory=create_dialog,
    )

    controller.show_restart_required_dialog()

    assert dialog_calls == []

    controller.dispose()
    button.close()
