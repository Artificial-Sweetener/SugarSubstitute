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

"""Present and execute the duplicate-launch decision before app handoff."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog
from qfluentwidgets import Dialog  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.ui.launcher_theme import (
    configure_launcher_theme,
)
from sugarsubstitute_shared.application_instance_control import (
    ApplicationShutdownRequestResult,
    request_active_application_shutdown,
)
from sugarsubstitute_shared.application_instance_lease import ApplicationInstanceLease


def negotiate_active_application(
    *,
    layout: InstallLayout,
    locale_override: str | None,
) -> bool:
    """Return whether the caller may retry launch after closing the active app."""

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    application = cast(QApplication, application)
    application.setWindowIcon(launcher_icon())
    configure_launcher_theme()
    localization_runtime = build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override=locale_override,
    )
    _ = localization_runtime
    if not _confirm_close_running_instance():
        return False
    result = request_active_application_shutdown(layout.root)
    if result is not ApplicationShutdownRequestResult.ACCEPTED:
        _show_manual_close_required()
        return False
    return _wait_for_instance_exit(layout.root)


def _confirm_close_running_instance() -> bool:
    """Ask whether the current app should close before this launch continues."""

    dialog = _build_active_instance_dialog()
    return bool(dialog.exec() == QDialog.DialogCode.Accepted)


def _build_active_instance_dialog() -> Dialog:
    """Build the Fluent duplicate-instance decision with safe keyboard defaults."""

    dialog = Dialog(
        launcher_text("Substitute is already running"),
        launcher_text(
            "Only one instance of Substitute is supported at a time. "
            "Would you like to close the running instance and start this one?"
        ),
    )
    dialog.setObjectName("activeApplicationDialog")
    dialog.setWindowTitle(launcher_text("Substitute is already running"))
    dialog.setWindowIcon(launcher_icon())
    dialog.yesButton.setText(launcher_text("Close Substitute and start"))
    dialog.cancelButton.setText(launcher_text("Cancel"))
    dialog.yesButton.setDefault(True)
    dialog.setFixedSize(560, 240)
    return dialog


def _show_manual_close_required() -> None:
    """Explain that the active app could not receive graceful shutdown."""

    dialog = Dialog(
        launcher_text("Substitute could not close the running instance"),
        launcher_text(
            "Close the running Substitute window yourself, then start Substitute again."
        ),
    )
    dialog.setWindowTitle(
        launcher_text("Substitute could not close the running instance")
    )
    dialog.setWindowIcon(launcher_icon())
    dialog.yesButton.setText(launcher_text("OK"))
    dialog.hideCancelButton()
    dialog.setFixedSize(560, 220)
    dialog.exec()


def _wait_for_instance_exit(install_root: Path, *, timeout_ms: int = 30000) -> bool:
    """Wait responsively for the active process to release OS ownership."""

    import time

    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if not ApplicationInstanceLease.owner_exists(install_root):
            return True
        QCoreApplication.processEvents()
        time.sleep(0.05)
    _show_manual_close_required()
    return False


__all__ = ["negotiate_active_application"]
