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

"""Verify session-specific recovery guidance on the production Qt dialog."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from launcher.sugarsubstitute_launcher.ui.instance_recovery_dialog import (
    present_instance_recovery_dialog,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceFailureReason,
)


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (
            ApplicationInstanceFailureReason.UNAVAILABLE,
            "The existing SugarSubstitute instance did not present a usable window.",
        ),
        (
            ApplicationInstanceFailureReason.OTHER_SESSION,
            "SugarSubstitute is open in another Windows session.",
        ),
        (
            ApplicationInstanceFailureReason.SESSION_UNVERIFIED,
            "SugarSubstitute could not verify which Windows session owns the existing instance.",
        ),
    ],
)
def test_recovery_guidance_matches_reason_and_available_actions(
    qt_application_owner: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reason: ApplicationInstanceFailureReason,
    message: str,
) -> None:
    """Inspect real controls while replacing only modal execution, never showing UI."""
    dialogs: list[QMessageBox] = []

    def inspect_dialog(dialog: QMessageBox) -> int:
        """Read the composed dialog and simulate dismissing its modal boundary."""
        dialogs.append(dialog)
        assert dialog.text() == message
        destructive = [
            button
            for button in dialog.buttons()
            if dialog.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole
        ]
        assert destructive == []
        assert "unresponsive" not in dialog.informativeText()
        assert "end the existing" not in dialog.informativeText()
        if reason is ApplicationInstanceFailureReason.OTHER_SESSION:
            assert "Return to that" in dialog.informativeText()
        return int(QMessageBox.DialogCode.Rejected)

    monkeypatch.setattr(QMessageBox, "exec", inspect_dialog)
    try:
        assert (
            present_instance_recovery_dialog(
                layout=InstallLayout.from_root(tmp_path),
                reason=reason,
            )
            is InstanceRecoveryAction.EXIT
        )
        assert len(dialogs) == 1
    finally:
        for dialog in dialogs:
            dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
