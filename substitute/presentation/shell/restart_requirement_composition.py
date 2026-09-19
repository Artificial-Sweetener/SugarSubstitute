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

"""Compose the shell restart-requirement controller."""

from __future__ import annotations

from typing import Any, cast

from substitute.presentation.restart_requirements import RestartRequirementUiController


def compose_restart_requirement_ui_controller(shell: Any) -> object | None:
    """Attach the restart cart controller to the toolbar button when available."""

    button = getattr(shell, "pendingRestartButton", None)
    service = getattr(shell, "restart_requirement_service", None)
    actions = getattr(shell, "comfy_runtime_actions", None)
    restart_full_app = getattr(actions, "request_comfy_restart", None)
    if button is None or service is None or not callable(restart_full_app):
        return None
    return cast(
        object,
        RestartRequirementUiController(
            service=service,
            button=button,
            restart_full_app=restart_full_app,
            restart_window=lambda: _request_shell_gui_reload(shell),
            parent=shell,
        ),
    )


def _request_shell_gui_reload(shell: Any) -> None:
    """Invoke the current shell GUI reload callback when the restart cart asks."""

    reload_gui = getattr(shell, "request_full_gui_reload", None)
    if callable(reload_gui):
        reload_gui()


__all__ = ["compose_restart_requirement_ui_controller"]
