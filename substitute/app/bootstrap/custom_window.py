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

"""Define the main shell frame without forcing composition imports to load it."""

from __future__ import annotations

from collections.abc import Callable
import importlib
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    SubstituteWindowFrame,
)
from substitute.shared.logging.logger import get_logger, log_exception

if TYPE_CHECKING:
    from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController


_LOGGER = get_logger("app.bootstrap.custom_window")
ShutdownRequest = Callable[[QWidget | None], None]


class CustomWindow(SubstituteWindowFrame):
    """Render the main application shell frame with custom title bar wiring."""

    def __init__(
        self,
        *,
        appearance_runtime: AppearanceRuntimeController,
        shutdown_request: ShutdownRequest | None = None,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA_ALT,
        create_body_material_surface: bool = False,
    ) -> None:
        """Configure the frameless shell style and titlebar menu container."""

        super().__init__(
            create_menu_container=True,
            create_comfy_output_toggle=True,
            create_generation_action_cluster=True,
            create_startup_diagnostics_button=True,
            create_app_orb_menu=True,
            backdrop_mode=backdrop_mode,
            create_body_material_surface=create_body_material_surface,
        )
        self._appearance_runtime = appearance_runtime
        self._shutdown_request = shutdown_request
        self._allow_direct_close = False
        self._quit_application_on_close = True
        self._substitute_main_window: QWidget | None = None

    def allow_direct_close(self) -> None:
        """Permit the final Qt close event once coordinated shutdown has finished."""

        self._allow_direct_close = True

    def closeEvent(self, event: Any) -> None:
        """Quit the QApplication explicitly so cleanup hooks always run."""

        if self._shutdown_request is not None and not self._allow_direct_close:
            event.ignore()
            self._shutdown_request(self)
            return
        app = QApplication.instance()
        should_quit_application = getattr(self, "_quit_application_on_close", True)
        if app is not None and should_quit_application:
            try:
                app.quit()
            except Exception:
                log_exception(_LOGGER, "Failed to request app quit from close event")
        event.accept()
        super().closeEvent(event)

    def suppress_app_quit_on_close(self) -> None:
        """Keep shell-frame disposal from requesting a full application quit."""

        self._quit_application_on_close = False

    def reload_shell_backdrop_from_preferences(self) -> CustomWindow:
        """Reload the outer shell frame so a persisted backdrop change can apply."""

        composition = importlib.import_module("substitute.app.bootstrap.composition")
        reload_shell_frame = cast(
            Callable[[CustomWindow], CustomWindow],
            getattr(composition, "reload_shell_frame"),
        )
        return reload_shell_frame(self)


__all__ = ["CustomWindow", "ShutdownRequest"]
