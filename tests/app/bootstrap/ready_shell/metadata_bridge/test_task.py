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

"""Tests for ready-shell startup task orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)

from ..support.restore_signals import _Signal
from ..support.trace import _patch_trace

PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_wire_ready_shell_metadata_bridge_delegates_to_metadata_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell metadata task should delegate bridge wiring to its owner."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    bridge = _SignalBridge()
    registered: list[object] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    def bridge_factory(parent: object) -> ModelMetadataUpdateSignalBridgeProtocol:
        """Return the bridge for the expected shell frame."""

        assert parent is shell_frame
        return cast(ModelMetadataUpdateSignalBridgeProtocol, bridge)

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge(
        startup_cancelled=False,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=registered.append,
        main_window_for_shell=lambda parent: (
            main_window if parent is shell_frame else object()
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert cast(object, wired) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_wire_ready_shell_metadata_bridge_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not construct metadata bridge collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge(
        startup_cancelled=True,
        shell_frame=object(),
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda _bridge: calls.append("register"),
        main_window_for_shell=lambda _parent: calls.append("main_window"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert calls == []
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_wire_ready_shell_metadata_bridge_task_records_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell metadata task should store the wired metadata bridge."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    bridge = _SignalBridge()
    registered: list[object] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge_task(
        startup_cancelled=False,
        shell_frame=shell_frame,
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            bridge,
        ),
        register_bridge=registered.append,
        main_window_for_shell=lambda _parent: main_window,
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert cast(object, wired) is bridge
    assert len(recorded_bridges) == 1
    assert cast(object, recorded_bridges[0]) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_wire_ready_shell_metadata_bridge_task_records_skip_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped ready-shell metadata task should store the skipped bridge result."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge_task(
        startup_cancelled=True,
        shell_frame=object(),
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda _bridge: calls.append("register"),
        main_window_for_shell=lambda _parent: calls.append("main_window"),
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert recorded_bridges == [None]
    assert calls == []
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_metadata_bridge_task_uses_live_shell_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata bridge task should read shell state when it runs."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    shell_state: list[object | None] = [None]
    bridge = _SignalBridge()
    registered: list[object] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    task = ready_shell_controller.ReadyShellMetadataBridgeTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        bridge_factory=lambda parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            bridge if parent is shell_frame else _SignalBridge(),
        ),
        register_bridge=registered.append,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.wire()

    assert skipped is None
    assert recorded_bridges == [None]
    assert registered == []

    shell_state[0] = shell_frame

    wired = task.wire()

    assert cast(object, wired) is bridge
    assert cast(object, recorded_bridges[1]) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "no_shell_frame"}),
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_create_ready_shell_metadata_bridge_task_returns_task() -> None:
    """Metadata bridge task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_metadata_bridge_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda bridge: bridge,
        main_window_for_shell=lambda _frame: object(),
        set_metadata_update_bridge=lambda _bridge: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellMetadataBridgeTask)


class _SignalBridge:
    """Expose a metadata-updated signal."""

    def __init__(self) -> None:
        """Create the signal double."""

        self.model_updated = _Signal()

    def emit_model_updated(self, _event: object) -> None:
        """Satisfy the metadata bridge protocol."""


class _MetadataSurfaceRefreshController:
    """Expose the model metadata update callback."""

    def handle_model_metadata_updated(self, _event: object) -> None:
        """Accept one model metadata update event."""


class _MetadataMainWindow:
    """Expose the metadata surface refresh controller."""

    def __init__(
        self,
        controller: _MetadataSurfaceRefreshController,
    ) -> None:
        """Store the controller double."""

        self.model_metadata_surface_refresh_controller = controller
