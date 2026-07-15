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

"""Coordinate startup model metadata progress presentation."""

from __future__ import annotations

from collections.abc import Callable, MutableSequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.managed_target_activation import (
    fan_out_splash_and_shell_output,
)
from substitute.app.bootstrap.model_metadata_refresh import (
    ModelMetadataRefreshServiceFactory,
)
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.application.model_metadata import ModelMetadataRefreshEvent


class ModelMetadataUpdateBridgeProtocol(Protocol):
    """Forward model metadata update events to the shell thread."""

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Forward one model metadata update event."""


class ModelMetadataUpdateSignalProtocol(Protocol):
    """Connect shell-thread metadata update consumers."""

    def connect(
        self, callback: Callable[[ModelMetadataRefreshEvent], object]
    ) -> object:
        """Connect one model metadata update callback."""


class ModelMetadataUpdateSignalBridgeProtocol(
    ModelMetadataUpdateBridgeProtocol, Protocol
):
    """Bridge metadata updates and expose a connectable Qt-compatible signal."""

    model_updated: ModelMetadataUpdateSignalProtocol


class StartupModelMetadataRefreshHandleProtocol(Protocol):
    """Track one startup metadata refresh lifetime."""

    def start(self) -> None:
        """Start refresh work."""

    def cancel(self) -> None:
        """Request refresh cancellation."""

    def shutdown(self) -> None:
        """Release refresh resources."""


class StartupModelMetadataRefreshHandleFactory(Protocol):
    """Create one startup metadata refresh handle."""

    def __call__(
        self,
        *,
        service_factory: ModelMetadataRefreshServiceFactory,
        progress_sink: StartupModelMetadataProgressSink,
        finished_callback: Callable[[], None] | None,
    ) -> StartupModelMetadataRefreshHandleProtocol:
        """Return one unstarted metadata refresh handle."""


@dataclass
class StartupModelMetadataRefreshState:
    """Track whether the startup metadata refresh has already been started."""

    started: bool = False


def wire_model_metadata_update_bridge(
    *,
    startup_cancelled: bool,
    shell_frame: object | None,
    bridge_factory: Callable[[object], ModelMetadataUpdateSignalBridgeProtocol],
    register_bridge: Callable[[object], object],
    main_window_for_shell: Callable[[object], object],
    trace_fields: Callable[[], dict[str, object]],
) -> ModelMetadataUpdateSignalBridgeProtocol | None:
    """Create and connect the shell-thread model metadata update bridge."""

    trace_mark("wire_metadata_bridge_task.start", **trace_fields())
    if startup_cancelled:
        trace_mark("wire_metadata_bridge_task.skip", reason="startup_cancelled")
        return None
    if shell_frame is None:
        trace_mark("wire_metadata_bridge_task.skip", reason="no_shell_frame")
        return None

    metadata_update_bridge = bridge_factory(shell_frame)
    register_bridge(metadata_update_bridge)
    main_window = main_window_for_shell(shell_frame)
    metadata_surface_refresh_controller = getattr(
        main_window,
        "model_metadata_surface_refresh_controller",
        None,
    )
    handle_metadata_update = getattr(
        metadata_surface_refresh_controller,
        "handle_model_metadata_updated",
        None,
    )
    if callable(handle_metadata_update):
        metadata_update_bridge.model_updated.connect(
            cast(Callable[[ModelMetadataRefreshEvent], object], handle_metadata_update)
        )
    trace_mark(
        "wire_metadata_bridge_task.end",
        connected=callable(handle_metadata_update),
        **trace_fields(),
    )
    return metadata_update_bridge


class StartupModelMetadataProgressSink:
    """Forward metadata refresh progress to splash and shell console history."""

    def __init__(
        self,
        *,
        splash: LaunchSplashClient | None,
        comfy_output_stream: Any,
        update_bridge: ModelMetadataUpdateBridgeProtocol | None = None,
    ) -> None:
        """Initialize the sink with the same targets used for Comfy startup output."""

        self._splash = splash
        self._comfy_output_stream = comfy_output_stream
        self._update_bridge = update_bridge

    def emit_line(self, line: str) -> None:
        """Append one stable metadata progress line."""

        trace_mark("model_metadata_refresh.progress.line", line=line)
        fan_out_splash_and_shell_output(
            splash=self._splash,
            comfy_output_stream=self._comfy_output_stream,
            line=line,
        )

    def emit_progress(self, line: str) -> None:
        """Append one transient metadata progress line."""

        trace_mark("model_metadata_refresh.progress.transient", line=line)
        fan_out_splash_and_shell_output(
            splash=self._splash,
            comfy_output_stream=self._comfy_output_stream,
            line=line,
        )

    def emit_model_updated(self, event: ModelMetadataRefreshEvent) -> None:
        """Forward one structured metadata update to the Qt bridge when present."""

        trace_mark(
            "model_metadata_refresh.progress.model_updated",
            kind=event.kind,
            thumbnail_updated=event.thumbnail_updated,
        )
        if self._update_bridge is not None:
            self._update_bridge.emit_model_updated(event)


def start_model_metadata_refresh(
    *,
    state: StartupModelMetadataRefreshState,
    startup_cancelled: bool,
    metadata_update_bridge: ModelMetadataUpdateBridgeProtocol | None,
    refreshes: MutableSequence[StartupModelMetadataRefreshHandleProtocol],
    service_factory: ModelMetadataRefreshServiceFactory,
    comfy_output_stream: Any,
    trace_fields: Callable[[], dict[str, object]],
    refresh_handle_factory: StartupModelMetadataRefreshHandleFactory,
) -> None:
    """Start background model metadata refresh without gating shell display."""

    trace_mark("model_metadata_refresh.start_requested", **trace_fields())
    if startup_cancelled:
        trace_mark("model_metadata_refresh.skip", reason="startup_cancelled")
        return
    if state.started or metadata_update_bridge is None:
        trace_mark(
            "model_metadata_refresh.skip",
            reason="already_started" if state.started else "no_metadata_bridge",
        )
        return
    finish_metadata_coalescing = getattr(
        metadata_update_bridge,
        "request_end_startup_coalescing",
        None,
    )
    refresh = refresh_handle_factory(
        service_factory=service_factory,
        progress_sink=StartupModelMetadataProgressSink(
            splash=None,
            comfy_output_stream=comfy_output_stream,
            update_bridge=metadata_update_bridge,
        ),
        finished_callback=finish_metadata_coalescing
        if callable(finish_metadata_coalescing)
        else None,
    )
    refreshes.append(refresh)
    refresh.start()
    state.started = True
    trace_mark("model_metadata_refresh.started")


__all__ = [
    "ModelMetadataUpdateBridgeProtocol",
    "ModelMetadataUpdateSignalBridgeProtocol",
    "ModelMetadataUpdateSignalProtocol",
    "StartupModelMetadataRefreshHandleFactory",
    "StartupModelMetadataRefreshHandleProtocol",
    "StartupModelMetadataProgressSink",
    "StartupModelMetadataRefreshState",
    "start_model_metadata_refresh",
    "wire_model_metadata_update_bridge",
]
