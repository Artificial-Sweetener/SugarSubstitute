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

"""Coordinate Comfy runtime shell actions against live presentation surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QMessageBox

from substitute.presentation.shell import comfy_settings_webview
from substitute.shared.logging.logger import get_logger, log_exception, log_warning

_LOGGER = get_logger("presentation.shell.comfy_runtime_actions")


class ComfyRuntimeActions:
    """Own shell actions for Comfy output, restart, and settings presentation."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose Comfy runtime actions should be applied."""

        self._shell = shell

    def is_comfy_output_panel_visible(self) -> bool:
        """Return whether the shell output panel currently occupies layout space."""

        return bool(self._shell.comfy_output_panel.is_panel_visible())

    def set_comfy_output_panel_visible(self, visible: bool) -> None:
        """Show or hide the shell output panel and emit state changes."""

        is_currently_visible = self.is_comfy_output_panel_visible()
        if visible == is_currently_visible:
            return
        self._shell.comfy_output_panel.set_panel_visible(visible)
        self._shell.comfy_output_panel_visibility_changed.emit(visible)
        self._shell.request_session_autosave()

    def set_comfy_restart_request_handler(
        self,
        handler: Callable[[], None] | None,
    ) -> None:
        """Set the bootstrap-owned handler for restarting ComfyUI."""

        self._shell._comfy_restart_request_handler = handler

    def request_comfy_restart(self) -> None:
        """Request a startup-equivalent ComfyUI restart from the shell."""

        handler = getattr(self._shell, "_comfy_restart_request_handler", None)
        if handler is None:
            log_warning(_LOGGER, "ComfyUI restart requested without a handler")
            QMessageBox.warning(
                self._shell,
                "Restart ComfyUI",
                "ComfyUI restart is not available in this session.",
            )
            return
        handler()

    def open_comfyui_settings_webview(self) -> None:
        """Open ComfyUI's native Settings dialog in a focused webview."""

        snapshot = self._shell.comfy_connection_settings_service.load_snapshot()
        endpoint = snapshot.target.endpoint
        if not comfy_settings_webview.WEBENGINE_AVAILABLE:
            comfy_settings_webview.log_webengine_unavailable()
            QMessageBox.warning(
                self._shell,
                "ComfyUI Settings",
                "Qt WebEngine is not available, so ComfyUI Settings cannot open here.",
            )
            return

        try:
            self._shell._comfy_settings_webview_dialog = (
                comfy_settings_webview.open_comfy_settings_webview(
                    endpoint=endpoint,
                    parent=self._shell,
                )
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Failed to open ComfyUI Settings webview",
                host=endpoint.host,
                port=endpoint.port,
            )
            QMessageBox.warning(
                self._shell,
                "ComfyUI Settings",
                "ComfyUI Settings could not be opened in the embedded webview.",
            )


def comfy_runtime_actions_for(shell: Any) -> ComfyRuntimeActions:
    """Return the composed Comfy runtime actions for a shell."""

    controller = getattr(shell, "comfy_runtime_actions", None)
    if isinstance(controller, ComfyRuntimeActions):
        return controller
    controller = ComfyRuntimeActions(shell)
    setattr(shell, "comfy_runtime_actions", controller)
    return controller


__all__ = [
    "ComfyRuntimeActions",
    "comfy_runtime_actions_for",
]
