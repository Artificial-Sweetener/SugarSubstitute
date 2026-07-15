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

"""Coordinate shell-owned model catalog update listening."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from collections.abc import Callable

from substitute.application.execution import TaskSubmitter
from substitute.application.model_metadata import BackendModelCatalogChangeEvent
from substitute.presentation.shell.main_window_dependencies import (
    MainWindowDependencies,
)
from substitute.presentation.shell.model_catalog_change_coordinator import (
    ModelCatalogChangeCoordinator,
)
from substitute.presentation.shell.model_catalog_update_bridge import (
    ModelCatalogUpdateBridge,
)
from substitute.presentation.shell.model_metadata_update_bridge import (
    ModelMetadataUpdateBridge,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.model_catalog_update_controller")


class ModelCatalogUpdateController:
    """Own live model catalog listener lifecycle and change fan-out."""

    def __init__(
        self,
        shell: Any,
        dependencies: MainWindowDependencies,
        *,
        node_definition_submitter: TaskSubmitter,
        close_node_definition_submitter: Callable[[], None],
    ) -> None:
        """Create bridges, coordinator, listener, and shutdown wiring."""

        self._shell = shell
        metadata_update_bridge = ModelMetadataUpdateBridge(shell)
        metadata_update_bridge.model_updated.connect(
            shell.model_metadata_surface_refresh_controller.handle_model_metadata_updated
        )
        self.metadata_update_bridge = metadata_update_bridge
        scoped_metadata_refresh_service = (
            dependencies.create_scoped_metadata_refresh_service(metadata_update_bridge)
        )
        self._change_coordinator = ModelCatalogChangeCoordinator(
            model_catalog_service=shell.model_catalog_service,
            model_choice_resolver=shell.model_choice_resolver,
            node_definition_gateway=shell.node_definition_gateway,
            lora_refresh_coordinator=(
                shell.model_metadata_surface_refresh_controller.lora_refresh_coordinator
            ),
            scoped_metadata_refresh_service=scoped_metadata_refresh_service,
            submitter=node_definition_submitter,
            close_submitter=close_node_definition_submitter,
        )
        self._update_bridge = ModelCatalogUpdateBridge(shell)
        self._update_bridge.model_catalog_changed.connect(self.on_catalog_changed)
        self._listener = dependencies.create_model_catalog_event_listener(
            cast(Any, self._update_bridge.emit_model_catalog_changed)
        )
        self._listener_started = False
        self._listener_start_scheduled = False
        self._shutdown_requested = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)
        self._start_when_backend_ready()

    def on_catalog_changed(self, event: object) -> None:
        """Invalidate model caches and route one backend model catalog change."""

        if not isinstance(event, BackendModelCatalogChangeEvent):
            log_warning(
                _LOGGER,
                "Ignored invalid model catalog change event",
                event_type=type(event).__name__,
            )
            return
        self._change_coordinator.handle_change(event)

    def start(self) -> None:
        """Start live model catalog update listening after construction returns."""

        self._listener_start_scheduled = False
        listener = self._listener
        if (
            not self._shutdown_requested
            and listener is not None
            and not self._listener_started
        ):
            listener.start()
            self._listener_started = True

    def stop(self) -> None:
        """Stop the background model catalog websocket listener and tasks."""

        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._listener_start_scheduled = False
        listener = self._listener
        if listener is not None:
            listener.stop()
            self._listener_started = False
        self._change_coordinator.shutdown()

    def _start_when_backend_ready(self) -> None:
        """Start immediately or wait for the shell backend-ready signal."""

        if getattr(self._shell, "_backend_state", "ready") == "ready":
            self._schedule_start()
            return
        state_signal = getattr(self._shell, "backend_state_changed", None)
        connect_state = getattr(state_signal, "connect", None)
        if callable(connect_state):
            connect_state(self._on_backend_state_changed)
        else:
            self._schedule_start()

    def _on_backend_state_changed(self, state: str) -> None:
        """Start the listener once the backend reaches ready state."""

        if state == "ready":
            self._schedule_start()

    def _schedule_start(self) -> None:
        """Schedule one delayed listener start."""

        if (
            self._shutdown_requested
            or self._listener_started
            or self._listener_start_scheduled
        ):
            return
        self._listener_start_scheduled = True
        QTimer.singleShot(0, self.start)


__all__ = ["ModelCatalogUpdateController"]
