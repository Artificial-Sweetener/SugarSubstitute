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

"""Verify the native duplicate-instance decision and graceful control path."""

from __future__ import annotations

from pathlib import Path

import pytest
from qfluentwidgets import Dialog  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher import active_instance_dialog
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_control import (
    ApplicationShutdownRequestResult,
)
from tests.launcher.support import launcher_test_application


def test_active_instance_dialog_uses_fluent_controls_with_safe_defaults() -> None:
    """Use branded Fluent controls with explicit close and cancel actions."""

    _ = launcher_test_application()

    dialog = active_instance_dialog._build_active_instance_dialog()

    assert isinstance(dialog, Dialog)
    assert dialog.objectName() == "activeApplicationDialog"
    assert dialog.yesButton.isDefault()
    assert dialog.yesButton.text() == "Close Substitute and start"
    assert dialog.cancelButton.text() == "Cancel"
    assert "one instance" in dialog.contentLabel.text().casefold()


def test_active_instance_negotiation_requests_and_waits_for_graceful_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Accepting the dialog should use IPC and wait for OS ownership release."""

    _ = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    requested: list[Path] = []
    waited: list[Path] = []

    def request_shutdown(root: Path) -> ApplicationShutdownRequestResult:
        """Record one application control request."""

        requested.append(root)
        return ApplicationShutdownRequestResult.ACCEPTED

    def wait_for_exit(root: Path) -> bool:
        """Record one lease-release wait."""

        waited.append(root)
        return True

    monkeypatch.setattr(
        active_instance_dialog,
        "_confirm_close_running_instance",
        lambda: True,
    )
    monkeypatch.setattr(
        active_instance_dialog,
        "request_active_application_shutdown",
        request_shutdown,
    )
    monkeypatch.setattr(
        active_instance_dialog,
        "_wait_for_instance_exit",
        wait_for_exit,
    )

    assert (
        active_instance_dialog.negotiate_active_application(
            layout=layout,
            locale_override="en",
        )
        is True
    )
    assert requested == [layout.root]
    assert waited == [layout.root]


def test_active_instance_negotiation_never_waits_after_unreachable_control(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unreachable owner must require manual closure instead of forced killing."""

    _ = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    warnings: list[bool] = []
    monkeypatch.setattr(
        active_instance_dialog,
        "_confirm_close_running_instance",
        lambda: True,
    )
    monkeypatch.setattr(
        active_instance_dialog,
        "request_active_application_shutdown",
        lambda _root: ApplicationShutdownRequestResult.UNAVAILABLE,
    )
    monkeypatch.setattr(
        active_instance_dialog,
        "_show_manual_close_required",
        lambda: warnings.append(True),
    )
    monkeypatch.setattr(
        active_instance_dialog,
        "_wait_for_instance_exit",
        lambda _root: pytest.fail("An unacknowledged owner must not be awaited."),
    )

    assert (
        active_instance_dialog.negotiate_active_application(
            layout=layout,
            locale_override="en",
        )
        is False
    )
    assert warnings == [True]
