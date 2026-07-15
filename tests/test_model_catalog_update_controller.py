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

"""Verify model catalog update lifecycle is outside MainWindow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.model_metadata import BackendModelCatalogChangeEvent
from substitute.presentation.shell import model_catalog_update_controller


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


class _Signal:
    """Capture connected callbacks for fake Qt signals."""

    def __init__(self) -> None:
        """Create an empty callback list."""

        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record a connected callback."""

        self.callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke connected callbacks."""

        for callback in self.callbacks:
            if callable(callback):
                callback(*args)


class _Listener:
    """Capture listener lifecycle calls."""

    def __init__(self) -> None:
        """Create stopped listener state."""

        self.started = False
        self.stopped = False

    def start(self) -> None:
        """Record that the listener started."""

        self.started = True

    def stop(self) -> None:
        """Record that the listener stopped."""

        self.stopped = True


class _FakeApplication:
    """Stand in for QApplication during controller construction."""

    aboutToQuit = _Signal()

    @classmethod
    def instance(cls) -> type[_FakeApplication]:
        """Return a fake application instance."""

        return cls


class _FakeTimer:
    """Capture delayed callbacks instead of invoking them."""

    single_shots: list[tuple[int, object]] = []

    @classmethod
    def singleShot(cls, delay_ms: int, callback: object) -> None:
        """Record one delayed callback."""

        cls.single_shots.append((delay_ms, callback))


class _FakeMetadataBridge:
    """Capture metadata update bridge wiring."""

    def __init__(self, parent: object) -> None:
        """Store parent and expose model update signal."""

        self.parent = parent
        self.model_updated = _Signal()


class _FakeUpdateBridge:
    """Capture model catalog update bridge wiring."""

    def __init__(self, parent: object) -> None:
        """Store parent and expose catalog change signal."""

        self.parent = parent
        self.model_catalog_changed = _Signal()
        self.emitted_events: list[BackendModelCatalogChangeEvent] = []

    def emit_model_catalog_changed(
        self,
        event: BackendModelCatalogChangeEvent,
    ) -> None:
        """Record an event listener callback."""

        self.emitted_events.append(event)


class _FakeChangeCoordinator:
    """Capture model catalog change coordination."""

    instances: list[_FakeChangeCoordinator] = []

    def __init__(self, **kwargs: object) -> None:
        """Store constructor collaborators."""

        self.kwargs = kwargs
        self.events: list[BackendModelCatalogChangeEvent] = []
        self.shutdown_called = False
        type(self).instances.append(self)

    def handle_change(self, event: BackendModelCatalogChangeEvent) -> None:
        """Record handled catalog changes."""

        self.events.append(event)

    def shutdown(self) -> None:
        """Record shutdown."""

        self.shutdown_called = True


class _RuntimeSubmitter:
    """Expose a close hook like runtime submitter routes."""

    def __init__(self) -> None:
        """Initialize close observations."""

        self.closed = False

    def close(self) -> None:
        """Record route closure."""

        self.closed = True


class _ExecutionRuntime:
    """Record runtime submitter requests."""

    def __init__(self) -> None:
        """Initialize submitter observations."""

        self.requests: list[tuple[str, str, object]] = []
        self.route = _RuntimeSubmitter()

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _RuntimeSubmitter:
        """Record and return one runtime submitter."""

        self.requests.append((name, owner_id, dispatcher))
        return self.route


class _Shell(SimpleNamespace):
    """Provide the shell surface consumed by the controller."""

    def __init__(self, *, backend_state: str = "ready") -> None:
        """Create shell collaborators."""

        super().__init__(
            _backend_state=backend_state,
            backend_state_changed=_Signal(),
            model_catalog_service=object(),
            model_choice_resolver=object(),
            node_definition_gateway=object(),
        )
        self.handled_metadata_events: list[object] = []
        self.model_metadata_surface_refresh_controller = SimpleNamespace(
            lora_refresh_coordinator=object(),
            handle_model_metadata_updated=self.handled_metadata_events.append,
        )


@pytest.fixture(autouse=True)
def controller_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Qt and coordinator collaborators with deterministic fakes."""

    _FakeApplication.aboutToQuit = _Signal()
    _FakeTimer.single_shots = []
    _FakeChangeCoordinator.instances = []
    monkeypatch.setattr(
        model_catalog_update_controller,
        "QApplication",
        _FakeApplication,
    )
    monkeypatch.setattr(model_catalog_update_controller, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        model_catalog_update_controller,
        "ModelMetadataUpdateBridge",
        _FakeMetadataBridge,
    )
    monkeypatch.setattr(
        model_catalog_update_controller,
        "ModelCatalogUpdateBridge",
        _FakeUpdateBridge,
    )
    monkeypatch.setattr(
        model_catalog_update_controller,
        "ModelCatalogChangeCoordinator",
        _FakeChangeCoordinator,
    )


def _event() -> BackendModelCatalogChangeEvent:
    """Create one backend catalog change event."""

    return BackendModelCatalogChangeEvent(
        schema_version=1,
        revision="rev",
        previous_revision="old",
        generated_at="2026-06-24T00:00:00Z",
        reason="sync",
        kinds=("loras",),
        affected_node_classes=("LoraLoader",),
        added=(),
        removed=(),
        modified=(),
    )


def _controller(
    shell: _Shell | None = None,
    listener: _Listener | None = None,
) -> model_catalog_update_controller.ModelCatalogUpdateController:
    """Create a controller with test fakes."""

    chosen_listener = listener or _Listener()
    dependencies = SimpleNamespace(
        create_scoped_metadata_refresh_service=lambda bridge: object(),
        create_model_catalog_event_listener=lambda callback: chosen_listener,
    )
    submitter = _RuntimeSubmitter()
    return model_catalog_update_controller.ModelCatalogUpdateController(
        shell or _Shell(),
        dependencies,  # type: ignore[arg-type]
        node_definition_submitter=submitter,  # type: ignore[arg-type]
        close_node_definition_submitter=submitter.close,
    )


def test_controller_wires_bridges_listener_and_shutdown() -> None:
    """Verify model catalog lifecycle setup moved out of MainWindow."""

    shell = _Shell()
    listener = _Listener()
    controller = _controller(shell, listener)

    metadata_update_bridge = cast(Any, controller.metadata_update_bridge)
    update_bridge = cast(Any, controller._update_bridge)
    assert metadata_update_bridge.parent is shell
    assert metadata_update_bridge.model_updated.callbacks == [
        shell.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert update_bridge.parent is shell
    assert update_bridge.model_catalog_changed.callbacks == [
        controller.on_catalog_changed
    ]
    assert _FakeApplication.aboutToQuit.callbacks == [controller.stop]
    assert _FakeTimer.single_shots == [(0, controller.start)]
    controller.start()
    controller.stop()
    assert listener.started is True
    assert listener.stopped is True
    assert _FakeChangeCoordinator.instances[0].shutdown_called is True


def test_listener_waits_until_backend_ready() -> None:
    """Verify websocket listening does not start before managed backend readiness."""

    shell = _Shell(backend_state="starting")
    listener = _Listener()
    controller = _controller(shell, listener)

    assert _FakeTimer.single_shots == []
    assert listener.started is False
    shell.backend_state_changed.emit("starting")
    assert _FakeTimer.single_shots == []

    shell.backend_state_changed.emit("ready")
    assert _FakeTimer.single_shots == [(0, controller.start)]
    cast(Any, _FakeTimer.single_shots[0][1])()

    assert listener.started is True


def test_listener_ready_signal_start_is_idempotent() -> None:
    """Verify repeated backend-ready projections do not start multiple listeners."""

    shell = _Shell(backend_state="starting")
    listener = _Listener()
    controller = _controller(shell, listener)

    shell.backend_state_changed.emit("ready")
    shell.backend_state_changed.emit("ready")

    assert _FakeTimer.single_shots == [(0, controller.start)]
    cast(Any, _FakeTimer.single_shots[0][1])()
    controller.start()
    assert listener.started is True


def test_scheduled_listener_start_is_cancelled_by_shutdown() -> None:
    """A queued start callback should not revive a detached shell listener."""

    listener = _Listener()
    controller = _controller(_Shell(), listener)
    scheduled_start = cast(Any, _FakeTimer.single_shots[0][1])

    controller.stop()
    scheduled_start()

    assert listener.started is False
    assert listener.stopped is True


def test_valid_catalog_change_routes_to_change_coordinator() -> None:
    """Verify valid backend events reach the change coordinator."""

    controller = _controller()
    event = _event()

    controller.on_catalog_changed(event)

    assert _FakeChangeCoordinator.instances[0].events == [event]


def test_invalid_catalog_change_is_ignored() -> None:
    """Verify invalid payloads do not reach model catalog coordination."""

    controller = _controller()

    controller.on_catalog_changed(object())

    assert _FakeChangeCoordinator.instances[0].events == []


def test_main_window_delegates_model_catalog_update_lifecycle() -> None:
    """Verify MainWindow no longer owns model catalog listener lifecycle methods."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    composition_source = (
        MAIN_WINDOW_SOURCE.parent / "main_window_composition.py"
    ).read_text(encoding="utf-8")

    assert "ModelCatalogUpdateController(" in composition_source
    assert "def _configure_model_catalog_updates" not in source
    assert "def _on_model_catalog_changed" not in source
    assert "def _start_model_catalog_event_listener" not in source
    assert "def _stop_model_catalog_event_listener" not in source
    assert "model_catalog_update_controller.stop()" not in source
