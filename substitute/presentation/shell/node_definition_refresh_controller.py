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

"""Coordinate shell refresh work after live node-definition changes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QTimer

from substitute.application.ports import (
    NodeDefinitionRefreshEvent,
    ObservableNodeDefinitionGateway,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.node_definition_refresh_controller")


class NodeDefinitionRefreshController:
    """Bridge, coalesce, and apply live node-definition refresh events."""

    def __init__(self, shell: Any) -> None:
        """Connect shell signals and subscribe to observable node definitions."""

        self._shell = shell
        self._pending_node_classes: set[str] = set()
        self._rebuild_scheduled = False
        self._unsubscribe: Callable[[], None] | None = None
        shell.node_definition_refreshed.connect(self.queue_refresh)
        self._unsubscribe = self._subscribe_refreshes()

    def dispose(self) -> None:
        """Detach long-lived node-definition observers."""

        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def queue_refresh(self, event: object) -> None:
        """Coalesce available node-definition refresh events for UI handling."""

        if not isinstance(event, NodeDefinitionRefreshEvent):
            log_warning(
                _LOGGER,
                "Ignored invalid node definition refresh event",
                event_type=type(event).__name__,
            )
            return
        if not event.available:
            return
        self._pending_node_classes.add(event.node_class)
        if self._rebuild_scheduled:
            return
        self._rebuild_scheduled = True
        trace_mark(
            "main_window.drain_node_definition_refresh_events",
            delay_ms=0,
        )
        QTimer.singleShot(0, self.drain_refreshes)

    def drain_refreshes(self) -> None:
        """Refresh active behavior and override presentation for coalesced classes."""

        trace_mark(
            "main_window.drain_node_definition_refresh_events.start",
            pending_count=len(self._pending_node_classes),
        )
        self._rebuild_scheduled = False
        refreshed_node_classes = tuple(sorted(self._pending_node_classes))
        self._pending_node_classes.clear()
        if not refreshed_node_classes:
            trace_mark(
                "main_window.drain_node_definition_refresh_events.skip",
                reason="no_refreshed_node_classes",
            )
            return
        self.refresh_active_overrides(
            refreshed_node_classes=refreshed_node_classes,
        )
        trace_mark(
            "main_window.drain_node_definition_refresh_events.end",
            refreshed_node_classes=refreshed_node_classes,
        )

    def refresh_active_overrides(
        self,
        *,
        refreshed_node_classes: tuple[str, ...],
    ) -> None:
        """Rebuild active behavior metadata and override controls."""

        workflow_id = str(
            getattr(self._shell.workflow_session_service, "active_workflow_id", "")
        )
        active_panel = self._shell.active_editor_panel
        active_manager = self._shell.active_override_manager
        log_info(
            _LOGGER,
            "Refreshing active override presentation after node definition update",
            active_workflow_id=workflow_id,
            refreshed_node_classes=refreshed_node_classes,
            active_editor_panel_present=active_panel is not None,
            active_override_manager_present=active_manager is not None,
        )
        if active_panel is None or active_manager is None:
            return

        projection_rebuilt = False
        refresh_projection = getattr(
            active_panel,
            "refresh_projection_after_node_definition_update",
            None,
        )
        if callable(refresh_projection):
            projection_rebuilt = bool(
                refresh_projection(refreshed_node_classes=refreshed_node_classes)
            )
        refresh_behavior = getattr(active_panel, "refresh_node_behavior_state", None)
        if callable(refresh_behavior) and not projection_rebuilt:
            refresh_behavior(
                reason="node_definition_changed",
                use_cached_snapshot=False,
            )
        rebuild_menu = getattr(active_manager, "rebuild_override_menu", None)
        if callable(rebuild_menu):
            rebuild_menu()
        rebuild_controls = getattr(
            active_manager,
            "rebuild_active_override_controls",
            None,
        )
        if callable(rebuild_controls):
            rebuild_controls()

    def _subscribe_refreshes(self) -> Callable[[], None] | None:
        """Bridge observable node-definition refresh events onto the Qt thread."""

        gateway = self._shell.node_definition_gateway
        if not isinstance(gateway, ObservableNodeDefinitionGateway):
            return None

        def emit_refresh(event: NodeDefinitionRefreshEvent) -> None:
            """Forward refresh events through Qt signal delivery."""

            self._shell.node_definition_refreshed.emit(event)

        return gateway.add_refresh_observer(emit_refresh)


__all__ = ["NodeDefinitionRefreshController"]
