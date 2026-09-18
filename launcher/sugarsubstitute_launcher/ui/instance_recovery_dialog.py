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

"""Present recovery choices for an unreachable active application instance."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceFailureReason,
)


def present_instance_recovery_dialog(
    *,
    layout: InstallLayout,
    reason: ApplicationInstanceFailureReason,
) -> InstanceRecoveryAction:
    """Return an explicit action while keeping log access inside the modal."""

    while True:
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(launcher_text("SugarSubstitute did not open"))
        if reason is ApplicationInstanceFailureReason.OTHER_SESSION:
            dialog.setText(
                launcher_text("SugarSubstitute is open in another Windows session.")
            )
            dialog.setInformativeText(
                launcher_text(
                    "Return to that Windows session and close SugarSubstitute, then retry here."
                )
            )
        else:
            dialog.setText(
                launcher_text(
                    "SugarSubstitute could not verify which Windows session owns the existing instance."
                )
                if reason is ApplicationInstanceFailureReason.SESSION_UNVERIFIED
                else launcher_text(
                    "The existing SugarSubstitute instance did not present a usable window."
                )
            )
            dialog.setInformativeText(
                launcher_text("You can retry or open the launcher logs for details.")
            )
        retry_button = dialog.addButton(
            launcher_text("Retry"), QMessageBox.ButtonRole.AcceptRole
        )
        logs_button = dialog.addButton(
            launcher_text("Open launcher logs"),
            QMessageBox.ButtonRole.ActionRole,
        )
        exit_button = dialog.addButton(
            launcher_text("Exit"), QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDetailedText(launcher_text("Launcher logs: %1", layout.logs_dir))
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is retry_button:
            return InstanceRecoveryAction.RETRY
        if clicked is logs_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(layout.logs_dir)))
            continue
        if clicked is exit_button:
            return InstanceRecoveryAction.EXIT
        return InstanceRecoveryAction.EXIT


__all__ = ["present_instance_recovery_dialog"]
