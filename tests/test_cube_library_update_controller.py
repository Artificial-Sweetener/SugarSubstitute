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

"""Verify shell Cube Library update coordination lives outside MainWindow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.application.cube_library import (
    CubeLibraryUpdateReason,
    LoadedCubeUpdateAction,
    LoadedCubeUpdateCandidate,
    LoadedCubeUpdateSelection,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.presentation.shell import cube_library_update_controller


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


class _Signal:
    """Capture connected callbacks for a fake Qt signal."""

    def __init__(self) -> None:
        """Create an empty callback list."""

        self.callbacks: list[object] = []
        self.emit_count = 0

    def connect(self, callback: object) -> None:
        """Record a connected callback."""

        self.callbacks.append(callback)

    def emit(self, *_args: object) -> None:
        """Record signal emission and invoke callbacks."""

        self.emit_count += 1
        for callback in self.callbacks:
            if callable(callback):
                callback(*_args)


class _Listener:
    """Capture listener lifecycle calls."""

    def __init__(self) -> None:
        """Create a stopped listener."""

        self.started = False
        self.stopped = False
        self.start_count = 0

    def start(self) -> None:
        """Record that the listener started."""

        self.started = True
        self.start_count += 1

    def stop(self) -> None:
        """Record that the listener stopped."""

        self.stopped = True


class _FakeApplication:
    """Stand in for QApplication during controller construction."""

    active_window: object | None = None
    installed_filters: list[object] = []
    aboutToQuit = _Signal()

    @classmethod
    def instance(cls) -> type[_FakeApplication]:
        """Return a fake application instance."""

        return cls

    @classmethod
    def activeWindow(cls) -> object | None:
        """Return the configured active window."""

        return cls.active_window

    @classmethod
    def installEventFilter(cls, event_filter: object) -> None:
        """Record event-filter installation."""

        cls.installed_filters.append(event_filter)


class _FakeTimer:
    """Capture delayed callbacks instead of invoking them."""

    single_shots: list[tuple[int, object]] = []

    @classmethod
    def singleShot(cls, delay_ms: int, callback: object) -> None:
        """Record one delayed callback."""

        cls.single_shots.append((delay_ms, callback))


class _FakeCoordinator:
    """Avoid background refresh work while exposing coordinator callbacks."""

    created_kwargs: dict[str, object] = {}

    def __init__(self, **kwargs: object) -> None:
        """Capture coordinator collaborators."""

        type(self).created_kwargs = kwargs
        self.pending: tuple[LoadedCubeUpdateCandidate, ...] = ()
        self.refresh_requested = False
        self.queued: tuple[LoadedCubeUpdateCandidate, ...] = ()
        self.presented: tuple[LoadedCubeUpdateCandidate, ...] = ()
        self.resolved: tuple[LoadedCubeUpdateCandidate, ...] = ()
        self.changed_updates: list[object] = []
        self.shutdown_requested = False

    def on_library_changed(self, update: object) -> None:
        """Record library change notifications."""

        self.changed_updates.append(update)

    def collect_pending_on_focus(self) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return pending candidates for modal presentation."""

        return self.pending

    def mark_presented(
        self,
        candidates: tuple[LoadedCubeUpdateCandidate, ...],
    ) -> None:
        """Record presented candidates."""

        self.presented = candidates

    def mark_resolved(
        self,
        candidates: tuple[LoadedCubeUpdateCandidate, ...],
    ) -> None:
        """Record resolved candidates."""

        self.resolved = candidates

    def queue_pending(
        self,
        candidates: tuple[LoadedCubeUpdateCandidate, ...],
    ) -> None:
        """Record externally queued candidates."""

        self.queued = candidates

    def refresh_async(self) -> None:
        """Record startup refresh scheduling."""

        self.refresh_requested = True

    def shutdown(self) -> None:
        """Record coordinator shutdown."""

        self.shutdown_requested = True


class _FakeActions:
    """Capture update selections sent through the shell action boundary."""

    failures: tuple[LoadedCubeUpdateSelection, ...] = ()
    received: tuple[LoadedCubeUpdateSelection, ...] = ()

    def __init__(self, _view: object) -> None:
        """Accept the view dependency without using it."""

    def apply_update_selections(
        self,
        selections: tuple[LoadedCubeUpdateSelection, ...],
    ) -> tuple[LoadedCubeUpdateSelection, ...]:
        """Record selections and return configured failures."""

        type(self).received = selections
        return type(self).failures


class _CubeLoadService:
    """Provide cache invalidation and version listing for controller tests."""

    def __init__(self) -> None:
        """Create version and invalidation state."""

        self.invalidated = False

    def invalidate_catalog_cache(self) -> None:
        """Record catalog invalidation."""

        self.invalidated = True

    def list_cube_versions(self, cube_id: str) -> tuple[str, ...]:
        """Return deterministic versions or raise for one cube."""

        if cube_id == "broken":
            raise RuntimeError("backend unavailable")
        return ("1.0.0", "2.0.0")


class _SnapshotCapture:
    """Provide workflow labels through the shell snapshot capture adapter."""

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return a predictable workflow label."""

        return f"Workflow {workflow_id}"


class _Shell(SimpleNamespace):
    """Provide the shell surface consumed by the controller."""

    def __init__(self, *, backend_state: str = "ready") -> None:
        """Create shell collaborators and signals."""

        super().__init__(
            _backend_state=backend_state,
            backend_state_changed=_Signal(),
            cube_library_updates_pending=_Signal(),
            cube_library_follow_latest_updates_requested=_Signal(),
            workflow_session_service=SimpleNamespace(workflows={"wf": object()}),
            session_snapshot_capture_adapter=_SnapshotCapture(),
            cube_load_service=_CubeLoadService(),
            autosave_count=0,
        )

    def request_session_autosave(self) -> None:
        """Record autosave requests."""

        self.autosave_count += 1

    def window(self) -> object:
        """Return the owning shell window."""

        return self


@pytest.fixture(autouse=True)
def controller_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace Qt and background collaborators with deterministic fakes."""

    _FakeApplication.active_window = None
    _FakeApplication.installed_filters = []
    _FakeApplication.aboutToQuit = _Signal()
    _FakeTimer.single_shots = []
    _FakeActions.failures = ()
    _FakeActions.received = ()
    monkeypatch.setattr(
        cube_library_update_controller,
        "QApplication",
        _FakeApplication,
    )
    monkeypatch.setattr(cube_library_update_controller, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        cube_library_update_controller,
        "CubeLibraryUpdateCoordinator",
        _FakeCoordinator,
    )
    monkeypatch.setattr(
        cube_library_update_controller,
        "WorkspaceCubeUpdateActions",
        _FakeActions,
    )


def _candidate(cube_id: str = "cube") -> LoadedCubeUpdateCandidate:
    """Create one update candidate."""

    return LoadedCubeUpdateCandidate(
        workflow_id="wf",
        workflow_name="Workflow wf",
        cube_alias="Cube",
        cube_id=cube_id,
        current_version="1.0.0",
        latest_version="2.0.0",
        catalog_revision="rev",
        display_name="Cube",
        reason=CubeLibraryUpdateReason.VERSION_DRIFT,
        update_policy=CubeUpdatePolicy.PINNED,
    )


def _dependencies(listener: _Listener) -> SimpleNamespace:
    """Create controller dependencies."""

    return SimpleNamespace(
        cube_library_client=object(),
        create_cube_library_event_listener=lambda callback: listener,
    )


def _controller(
    shell: _Shell | None = None,
    listener: _Listener | None = None,
) -> cube_library_update_controller.CubeLibraryUpdateController:
    """Create a controller with test fakes."""

    return cube_library_update_controller.CubeLibraryUpdateController(
        shell or _Shell(),
        _dependencies(listener or _Listener()),  # type: ignore[arg-type]
        refresh_submitter=ImmediateTaskSubmitter(),
    )


def test_controller_wires_listener_signals_and_event_filter() -> None:
    """Verify live update setup moved out of MainWindow."""

    shell = _Shell()
    listener = _Listener()
    controller = _controller(shell, listener)
    workflow_name_provider = cast(
        Any,
        _FakeCoordinator.created_kwargs["workflow_name_provider"],
    )

    assert _FakeCoordinator.created_kwargs["catalog_client"] is not None
    assert workflow_name_provider() == {"wf": "Workflow wf"}
    assert shell.cube_library_updates_pending.callbacks == [
        controller.on_updates_pending
    ]
    assert shell.cube_library_follow_latest_updates_requested.callbacks == [
        controller.apply_follow_latest_updates
    ]
    assert _FakeApplication.installed_filters == [shell]
    assert _FakeTimer.single_shots == [(0, controller.start_listener)]
    controller.start_listener()
    controller.stop_listener()
    assert listener.started is True
    assert listener.stopped is True
    assert cast(Any, controller.coordinator).shutdown_requested is True


def test_listener_waits_until_backend_ready() -> None:
    """Verify Cube Library websocket listening waits for backend readiness."""

    shell = _Shell(backend_state="starting")
    listener = _Listener()
    controller = _controller(shell, listener)

    assert _FakeTimer.single_shots == []
    assert listener.started is False
    shell.backend_state_changed.emit("starting")
    assert _FakeTimer.single_shots == []

    shell.backend_state_changed.emit("ready")
    assert _FakeTimer.single_shots == [(0, controller.start_listener)]
    cast(Any, _FakeTimer.single_shots[0][1])()

    assert listener.started is True


def test_listener_ready_signal_start_is_idempotent() -> None:
    """Verify repeated backend-ready projections do not duplicate listeners."""

    shell = _Shell(backend_state="starting")
    listener = _Listener()
    controller = _controller(shell, listener)

    shell.backend_state_changed.emit("ready")
    shell.backend_state_changed.emit("ready")

    assert _FakeTimer.single_shots == [(0, controller.start_listener)]
    cast(Any, _FakeTimer.single_shots[0][1])()
    controller.start_listener()
    assert listener.start_count == 1


def test_scheduled_listener_start_is_cancelled_by_shutdown() -> None:
    """A queued start callback should not revive a detached shell listener."""

    listener = _Listener()
    controller = _controller(_Shell(), listener)
    scheduled_start = cast(Any, _FakeTimer.single_shots[0][1])

    controller.stop_listener()
    scheduled_start()

    assert listener.started is False
    assert listener.stopped is True


def test_library_change_invalidates_cache_and_routes_to_coordinator() -> None:
    """Verify backend change events invalidate caches before coordination."""

    shell = _Shell()
    controller = _controller(shell)
    update = SimpleNamespace(
        catalog_revision="new",
        previous_catalog_revision="old",
        reason="sync",
    )

    controller.on_library_changed(update)

    assert shell.cube_load_service.invalidated is True
    coordinator = cast(Any, controller.coordinator)
    assert coordinator.changed_updates == [update]


def test_follow_latest_updates_apply_and_request_autosave() -> None:
    """Verify automatic selections use update actions and autosave on success."""

    shell = _Shell()
    controller = _controller(shell)
    selection = LoadedCubeUpdateSelection(
        candidate=_candidate(),
        action=LoadedCubeUpdateAction.FOLLOW_LATEST,
        target_version="2.0.0",
    )

    controller.apply_follow_latest_updates((selection,))

    assert _FakeActions.received == (selection,)
    assert shell.autosave_count == 1


def test_versions_are_listed_per_cube_and_failures_are_omitted() -> None:
    """Verify version lookup remains isolated behind the controller."""

    controller = _controller()
    candidates = (_candidate("cube"), _candidate("broken"))

    versions = controller.cube_versions_for_update_candidates(candidates)

    assert versions == {"cube": ("1.0.0", "2.0.0")}


def test_main_window_delegates_cube_library_update_lifecycle() -> None:
    """Verify MainWindow no longer owns Cube Library update lifecycle methods."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    composition_source = (
        MAIN_WINDOW_SOURCE.parent / "main_window_composition.py"
    ).read_text(encoding="utf-8")

    assert "CubeLibraryUpdateController(" in composition_source
    assert "def _configure_cube_library_updates" not in source
    assert "def _present_pending_cube_library_updates" not in source
    assert "def _schedule_cube_library_startup_update_check" not in source
    assert "cube_library_update_controller.present_pending_updates()" not in source
