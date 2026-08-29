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

"""Negotiate a foreign ComfyUI listener on the standard local endpoint."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QDialog
from qfluentwidgets import Dialog  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import render_application_text
from substitute.domain.onboarding import LocalComfyProcess
from substitute.infrastructure.comfy.local_process_gateway import (
    PsutilLocalComfyProcessGateway,
)
from substitute.infrastructure.comfy.managed_process_probe import is_endpoint_listening
from substitute.infrastructure.comfy.managed_process_query import get_listener_pid


_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8188


def negotiate_default_comfy_listener(
    *,
    ensure_theme: Callable[[], object] | None = None,
) -> bool:
    """Return whether startup may continue after checking only port 8188."""

    if not is_endpoint_listening(_DEFAULT_HOST, _DEFAULT_PORT):
        return True
    if ensure_theme is not None:
        ensure_theme()
    process = _verified_listener_process()
    if process is None:
        _show_manual_close_required()
        return False
    if not _confirm_close_comfy(process):
        return False
    result = PsutilLocalComfyProcessGateway().terminate((process,))
    if result.succeeded:
        return True
    _show_manual_close_required()
    return False


def _verified_listener_process() -> LocalComfyProcess | None:
    """Return the exact verified Comfy process listening on the default port."""

    listener_pid = get_listener_pid(_DEFAULT_HOST, _DEFAULT_PORT)
    if listener_pid is None:
        return None
    return PsutilLocalComfyProcessGateway().inspect(listener_pid)


def _confirm_close_comfy(process: LocalComfyProcess) -> bool:
    """Ask permission to close one revalidated default-port Comfy process."""

    dialog = _build_default_comfy_dialog(process)
    return bool(dialog.exec() == QDialog.DialogCode.Accepted)


def _build_default_comfy_dialog(
    process: LocalComfyProcess,
) -> Dialog:
    """Build the Fluent default-port conflict decision with explicit escape."""

    dialog = Dialog(
        _render(app_text("ComfyUI is already running")),
        _render(
            app_text(
                "ComfyUI is already running on the default port 8188. Substitute "
                "needs to start and control ComfyUI itself to work correctly."
            )
        )
        + "\n\n"
        + _render(app_text("Would you like Substitute to close ComfyUI and continue?")),
    )
    dialog.setObjectName("defaultComfyConflictDialog")
    dialog.setWindowTitle(_render(app_text("ComfyUI is already running")))
    dialog.yesButton.setText(_render(app_text("Close ComfyUI and continue")))
    dialog.cancelButton.setText(_render(app_text("Cancel")))
    dialog.yesButton.setDefault(True)
    dialog.setProperty("verifiedComfyWorkspace", str(process.workspace))
    dialog.setFixedSize(600, 280)
    return dialog


def _show_manual_close_required() -> None:
    """Explain that an unverified default-port listener cannot be terminated."""

    dialog = Dialog(
        _render(app_text("Close ComfyUI before starting Substitute")),
        _render(
            app_text(
                "ComfyUI is responding on the default port 8188, but Substitute "
                "could not verify its process safely. Close ComfyUI yourself, then "
                "start Substitute again."
            )
        ),
    )
    dialog.setWindowTitle(_render(app_text("Close ComfyUI before starting Substitute")))
    dialog.yesButton.setText(_render(app_text("OK")))
    dialog.hideCancelButton()
    dialog.setFixedSize(600, 250)
    dialog.exec()


def _render(text: ApplicationText) -> str:
    """Render app-owned preflight copy through the active localization owner."""

    return render_application_text(text)


__all__ = ["negotiate_default_comfy_listener"]
