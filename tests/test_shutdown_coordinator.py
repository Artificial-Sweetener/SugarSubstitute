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

"""Tests for coordinated shell shutdown orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from time import monotonic, sleep
from collections.abc import Callable, Iterator
from typing import Protocol, TypeVar

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap.execution_runtime import (
    ExecutionLaneConfig,
    ExecutionRuntime,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap import shutdown_coordinator as shutdown_module
from substitute.app.bootstrap.shutdown_coordinator import ShutdownCoordinator
from substitute.application.execution import TaskSubmitter
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher

TDialog = TypeVar("TDialog")


@pytest.fixture
def cleanup_submitter() -> Iterator[TaskSubmitter]:
    """Provide a real shutdown-lane submitter for coordinator tests."""

    QApplication.instance() or QApplication([])
    runtime = ExecutionRuntime(
        lane_configs=(
            ExecutionLaneConfig(
                name="shutdown",
                max_workers=1,
                queue_capacity=8,
                thread_name_prefix="substitute-shutdown-test",
            ),
        )
    )
    submitter = runtime.submitter(
        "shutdown",
        owner_id="shutdown_coordinator_test",
        dispatcher=QtOwnerThreadDispatcher(),
    )
    try:
        yield submitter
    finally:
        submitter.close()
        runtime.shutdown()


@dataclass
class _FakeApp:
    """Record application quit requests from the shutdown coordinator."""

    quit_calls: int = 0

    def quit(self) -> None:
        """Record one quit request."""

        self.quit_calls += 1


class _FakeProgressDialog:
    """Capture coordinator-driven progress dialog activity."""

    def __init__(self, event_log: list[str]) -> None:
        self.actions: list[str] = []
        self.thread_names: list[str] = []
        self._event_log = event_log

    def show(self) -> None:
        self._record("progress.show")

    def raise_(self) -> None:
        self._record("progress.raise")

    def activateWindow(self) -> None:
        self._record("progress.activate")

    def allow_close(self) -> None:
        self._record("progress.allow_close")

    def close(self) -> bool:
        self._record("progress.close")
        return True

    def _record(self, action: str) -> None:
        self.actions.append(action)
        self.thread_names.append(threading.current_thread().name)
        self._event_log.append(action)


class _FakeRecoveryDialog:
    """Capture coordinator-driven recovery dialog activity."""

    def __init__(self, event_log: list[str]) -> None:
        self.actions: list[str] = []
        self.thread_names: list[str] = []
        self._event_log = event_log
        self._retry_callback: Callable[[], None] | None = None
        self._force_close_callback: Callable[[], None] | None = None
        self.detail_text = ""

    def show(self) -> None:
        self._record("recovery.show")

    def raise_(self) -> None:
        self._record("recovery.raise")

    def activateWindow(self) -> None:
        self._record("recovery.activate")

    def allow_close(self) -> None:
        self._record("recovery.allow_close")

    def close(self) -> bool:
        self._record("recovery.close")
        return True

    def set_retry_callback(self, callback: Callable[[], None]) -> None:
        self._retry_callback = callback

    def set_force_close_callback(self, callback: Callable[[], None]) -> None:
        self._force_close_callback = callback

    def show_uncertain_outcome(self, detail_text: str) -> None:
        self.detail_text = detail_text
        self._record("recovery.uncertain")

    def show_failed_outcome(self, detail_text: str) -> None:
        self.detail_text = detail_text
        self._record("recovery.failed")

    def trigger_retry(self) -> None:
        assert self._retry_callback is not None
        self._retry_callback()

    def trigger_force_close(self) -> None:
        assert self._force_close_callback is not None
        self._force_close_callback()

    def _record(self, action: str) -> None:
        self.actions.append(action)
        self.thread_names.append(threading.current_thread().name)
        self._event_log.append(action)


class _DeletedDialog:
    """Mimic a Qt wrapper whose underlying C++ dialog has been deleted."""

    def __init__(self) -> None:
        """Initialize call counters."""

        self.raise_calls = 0
        self.activate_calls = 0

    def show(self) -> None:
        """Raise like a stale Qt wrapper."""

        raise RuntimeError("Internal C++ object already deleted.")

    def raise_(self) -> None:
        """Raise like a stale Qt wrapper."""

        self.raise_calls += 1
        raise RuntimeError("Internal C++ object already deleted.")

    def activateWindow(self) -> None:
        """Record activation attempts."""

        self.activate_calls += 1

    def allow_close(self) -> None:
        """Raise like a stale Qt wrapper."""

        raise RuntimeError("Internal C++ object already deleted.")

    def close(self) -> bool:
        """Raise like a stale Qt wrapper."""

        raise RuntimeError("Internal C++ object already deleted.")


class _FakeWindow(QWidget):
    """Record whether the shell was allowed to accept the final close event."""

    def __init__(self) -> None:
        super().__init__()
        self.allow_direct_close_calls = 0

    def allow_direct_close(self) -> None:
        """Record one permission to accept the final close event."""

        self.allow_direct_close_calls += 1


def test_shutdown_coordinator_fast_success_stays_invisible(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Fast successful cleanup should not instantiate any shutdown UI."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 100)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    progress_dialogs: list[_FakeProgressDialog] = []
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    event_log: list[str] = []
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog(event_log),
        ),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog(event_log),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert progress_dialogs == []
    assert recovery_dialogs == []
    assert coordinator.shutdown_in_progress is False


def test_shutdown_coordinator_success_enables_direct_close_before_quit(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Successful shutdown should hand the shell its direct-close permission."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    window = _FakeWindow()
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )

    coordinator.request_shutdown(window)
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert window.allow_direct_close_calls == 1


def test_shutdown_coordinator_runs_before_cleanup_hook_before_task(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Pre-cleanup hook should run synchronously before managed cleanup begins."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    events: list[str] = []

    def cleanup() -> ManagedComfyCleanupResult:
        events.append("cleanup")
        return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        before_cleanup=lambda: events.append("before_cleanup"),
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert events == ["before_cleanup", "cleanup"]


def test_shutdown_coordinator_continues_cleanup_when_before_hook_fails(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Session-save failures must not block managed Comfy cleanup."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    events: list[str] = []

    def before_cleanup() -> None:
        events.append("before_cleanup")
        raise RuntimeError("save failed")

    def cleanup() -> ManagedComfyCleanupResult:
        events.append("cleanup")
        return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        before_cleanup=before_cleanup,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert events == ["before_cleanup", "cleanup"]


def test_shutdown_coordinator_slow_success_shows_progress_after_threshold(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Slow successful cleanup should show exactly one delayed progress dialog."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    progress_dialogs: list[_FakeProgressDialog] = []
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    event_log: list[str] = []
    cleanup_release = threading.Event()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_release.wait(timeout=2)
        return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog(event_log),
        ),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog(event_log),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(progress_dialogs) == 1, qt_app)
    cleanup_release.set()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert progress_dialogs[0].actions.count("progress.show") == 1
    assert "progress.allow_close" in progress_dialogs[0].actions
    assert "progress.close" in progress_dialogs[0].actions
    assert recovery_dialogs == []


def test_shutdown_coordinator_ignores_duplicate_close_requests(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Repeated shutdown requests should not start a second cleanup task."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 250)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    cleanup_started = threading.Event()
    cleanup_release = threading.Event()
    cleanup_calls: list[int] = []
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _blocking_cleanup(
            cleanup_started=cleanup_started,
            cleanup_release=cleanup_release,
            cleanup_calls=cleanup_calls,
        ),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )

    coordinator.request_shutdown()
    assert cleanup_started.wait(timeout=2) is True
    coordinator.request_shutdown()
    cleanup_release.set()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert cleanup_calls == [1]


def test_shutdown_coordinator_duplicate_close_while_progress_visible_only_refocuses(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """A second close request during the slow path should only refocus progress UI."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    cleanup_started = threading.Event()
    cleanup_release = threading.Event()
    cleanup_calls: list[int] = []
    progress_dialogs: list[_FakeProgressDialog] = []
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _blocking_cleanup(
            cleanup_started=cleanup_started,
            cleanup_release=cleanup_release,
            cleanup_calls=cleanup_calls,
        ),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog([]),
        ),
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )

    coordinator.request_shutdown()
    assert cleanup_started.wait(timeout=2) is True
    _wait_for(lambda: len(progress_dialogs) == 1, qt_app)
    coordinator.request_shutdown()
    cleanup_release.set()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert cleanup_calls == [1]
    assert progress_dialogs[0].actions.count("progress.show") == 1
    assert progress_dialogs[0].actions.count("progress.raise") >= 2
    assert progress_dialogs[0].actions.count("progress.activate") >= 2


def test_shutdown_coordinator_duplicate_close_during_finalizing_does_not_refocus(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Duplicate close events during final app exit should not touch stale dialogs."""

    app = _FakeApp()
    progress_dialog = _DeletedDialog()
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: progress_dialog,
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )
    coordinator._progress_dialog = progress_dialog
    coordinator._ui_state = shutdown_module.ShutdownUiState.FINALIZING_EXIT

    coordinator.request_shutdown()

    assert progress_dialog.raise_calls == 0
    assert progress_dialog.activate_calls == 0


def test_shutdown_coordinator_forgets_deleted_dialog_during_duplicate_refocus(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """A stale Qt dialog wrapper should be forgotten instead of raising outward."""

    app = _FakeApp()
    progress_dialog = _DeletedDialog()
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: progress_dialog,
        recovery_dialog_factory=lambda _parent: _FakeRecoveryDialog([]),
    )
    coordinator._progress_dialog = progress_dialog
    coordinator._ui_state = shutdown_module.ShutdownUiState.RUNNING_VISIBLE

    coordinator.request_shutdown()

    assert progress_dialog.raise_calls == 1
    assert coordinator._progress_dialog is None


def test_shutdown_coordinator_uncertain_cleanup_shows_one_recovery_dialog(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Uncertain cleanup should produce exactly one recovery surface."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)

    assert app.quit_calls == 0
    assert recovery_dialogs[0].actions.count("recovery.show") == 1
    assert "recovery.uncertain" in recovery_dialogs[0].actions


def test_shutdown_coordinator_failed_cleanup_shows_one_recovery_dialog(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Failed cleanup should produce exactly one recovery surface."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=lambda: _cleanup_result(ManagedComfyCleanupOutcome.FAILURE),
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)

    assert app.quit_calls == 0
    assert recovery_dialogs[0].actions.count("recovery.show") == 1
    assert "recovery.failed" in recovery_dialogs[0].actions


def test_shutdown_coordinator_closes_progress_before_showing_recovery(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """The progress surface should close before the recovery dialog appears."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    event_log: list[str] = []
    progress_dialogs: list[_FakeProgressDialog] = []
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_release = threading.Event()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_release.wait(timeout=2)
        return _cleanup_result(ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog(event_log),
        ),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog(event_log),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(progress_dialogs) == 1, qt_app)
    cleanup_release.set()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)

    assert event_log.index("progress.close") < event_log.index("recovery.show")


def test_shutdown_coordinator_retry_starts_one_fresh_cleanup_attempt(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Retry should start a fresh cleanup attempt after the recovery dialog appears."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_calls: list[int] = []
    cleanup_results = [
        _cleanup_result(ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS),
        _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS),
    ]

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_calls.append(1)
        return cleanup_results.pop(0)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)
    recovery_dialogs[0].trigger_retry()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert len(cleanup_calls) == 2
    assert "recovery.close" in recovery_dialogs[0].actions


def test_shutdown_coordinator_force_close_exits_without_another_cleanup_attempt(
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Force-close should bypass any further cleanup attempts and quit immediately."""

    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_calls: list[int] = []
    skip_cleanup_calls: list[int] = []
    window = _FakeWindow()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_calls.append(1)
        return _cleanup_result(ManagedComfyCleanupOutcome.FAILURE)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        skip_cleanup_on_force_close=lambda: skip_cleanup_calls.append(1),
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown(window)
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)
    recovery_dialogs[0].trigger_force_close()
    _wait_for(lambda: app.quit_calls == 1, qt_app)

    assert len(cleanup_calls) == 1
    assert skip_cleanup_calls == [1]
    assert window.allow_direct_close_calls == 1


def test_shutdown_coordinator_updates_dialogs_only_on_ui_thread(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """All progress and recovery dialog mutations should stay on the main thread."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    cleanup_thread_names: list[str] = []
    event_log: list[str] = []
    progress_dialogs: list[_FakeProgressDialog] = []
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_release = threading.Event()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_thread_names.append(threading.current_thread().name)
        cleanup_release.wait(timeout=2)
        return _cleanup_result(ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog(event_log),
        ),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog(event_log),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(progress_dialogs) == 1, qt_app)
    cleanup_release.set()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app)

    assert cleanup_thread_names[0].startswith("substitute-shutdown-test")
    assert set(progress_dialogs[0].thread_names) == {"MainThread"}
    assert set(recovery_dialogs[0].thread_names) == {"MainThread"}


def test_shutdown_coordinator_times_out_cleanup_and_ignores_late_success(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Timeout recovery should appear without letting late cleanup auto-quit the app."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    monkeypatch.setattr(shutdown_module, "_CLEANUP_ATTEMPT_TIMEOUT_MS", 60)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    progress_dialogs: list[_FakeProgressDialog] = []
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_release = threading.Event()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_release.wait(timeout=2)
        return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _record_dialog(
            progress_dialogs,
            _FakeProgressDialog([]),
        ),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app, timeout_seconds=1.5)
    cleanup_release.set()
    _drain_events(qt_app, duration_seconds=0.2)

    assert len(progress_dialogs) == 1
    assert app.quit_calls == 0
    assert "recovery.failed" in recovery_dialogs[0].actions


def test_shutdown_coordinator_ignores_retry_while_timed_out_task_still_active(
    monkeypatch: pytest.MonkeyPatch,
    cleanup_submitter: TaskSubmitter,
) -> None:
    """Retry should not start a second cleanup task while timed-out cleanup is stuck."""

    monkeypatch.setattr(shutdown_module, "_SLOW_SHUTDOWN_THRESHOLD_MS", 25)
    monkeypatch.setattr(shutdown_module, "_CLEANUP_ATTEMPT_TIMEOUT_MS", 60)
    qt_app = QApplication.instance() or QApplication([])
    app = _FakeApp()
    recovery_dialogs: list[_FakeRecoveryDialog] = []
    cleanup_calls: list[int] = []
    cleanup_release = threading.Event()

    def cleanup() -> ManagedComfyCleanupResult:
        cleanup_calls.append(1)
        cleanup_release.wait(timeout=2)
        return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)

    coordinator = ShutdownCoordinator(
        app=app,
        cleanup=cleanup,
        cleanup_submitter=cleanup_submitter,
        progress_dialog_factory=lambda _parent: _FakeProgressDialog([]),
        recovery_dialog_factory=lambda _parent: _record_dialog(
            recovery_dialogs,
            _FakeRecoveryDialog([]),
        ),
    )

    coordinator.request_shutdown()
    _wait_for(lambda: len(recovery_dialogs) == 1, qt_app, timeout_seconds=1.5)
    recovery_dialogs[0].trigger_retry()
    _drain_events(qt_app, duration_seconds=0.1)
    cleanup_release.set()
    _drain_events(qt_app, duration_seconds=0.2)

    assert cleanup_calls == [1]
    assert app.quit_calls == 0


def _blocking_cleanup(
    *,
    cleanup_started: threading.Event,
    cleanup_release: threading.Event,
    cleanup_calls: list[int],
) -> ManagedComfyCleanupResult:
    """Run one deterministic blocking cleanup for coordinator tests."""

    cleanup_calls.append(1)
    cleanup_started.set()
    cleanup_release.wait(timeout=2)
    return _cleanup_result(ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS)


def _cleanup_result(
    outcome: ManagedComfyCleanupOutcome,
    *,
    technical_detail: str | None = None,
) -> ManagedComfyCleanupResult:
    """Build one lifecycle cleanup result for coordinator tests."""

    safe_detail_by_outcome = {
        ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED: (
            "No managed ComfyUI cleanup was required."
        ),
        ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS: "Shutdown finished cleanly.",
        ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS: (
            "Shutdown could not be confirmed before the verification timeout."
        ),
        ManagedComfyCleanupOutcome.FAILURE: (
            "The termination command timed out before completion."
        ),
    }
    user_detail_by_outcome = {
        ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED: (
            "No managed ComfyUI cleanup was required."
        ),
        ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS: (
            "Substitute finished closing cleanly."
        ),
        ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS: (
            "Substitute could not confirm that shutdown finished."
        ),
        ManagedComfyCleanupOutcome.FAILURE: (
            "Substitute could not finish closing completely."
        ),
    }
    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=outcome,
        managed_resource_present=outcome
        is not ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        live_process_present=True,
        metadata_present=True,
        used_persisted_metadata=False,
        termination_attempted=True,
        registry_cleared=outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        pid=123,
        host="127.0.0.1",
        port=8188,
        workspace=None,
        elapsed_ms=10,
        taskkill_timeout=outcome is ManagedComfyCleanupOutcome.FAILURE,
        verification_timeout=outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS,
        user_detail=user_detail_by_outcome[outcome],
        technical_detail=technical_detail or safe_detail_by_outcome[outcome],
        diagnostic_detail="raw diagnostic detail",
    )


def _record_dialog(dialogs: list[TDialog], dialog: TDialog) -> TDialog:
    """Append one fake dialog to the supplied collection and return it."""

    dialogs.append(dialog)
    return dialog


def _wait_for(
    predicate: Callable[[], bool],
    app: "_EventPumpProtocol",
    *,
    timeout_seconds: float = 2.0,
) -> None:
    """Pump Qt events until one predicate becomes true or the timeout elapses."""

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        sleep(0.01)
    app.processEvents()
    assert predicate()


class _EventPumpProtocol(Protocol):
    """Describe the minimal Qt event pump surface used by coordinator tests."""

    def processEvents(self) -> None:
        """Process pending Qt events."""


def _drain_events(
    app: "_EventPumpProtocol",
    *,
    duration_seconds: float,
) -> None:
    """Pump Qt events for a fixed interval to flush late cleanup completions."""

    deadline = monotonic() + duration_seconds
    while monotonic() < deadline:
        app.processEvents()
        sleep(0.01)
