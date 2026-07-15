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

"""Tests for process-lifetime application runtime service composition."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar, cast

import pytest
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap import runtime as runtime_module
from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController
from substitute.app.bootstrap.runtime import build_application_runtime_services
from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
)
from tests.execution_testing import ManualTaskHandle
from substitute.domain.appearance import default_appearance_preferences
from substitute.domain.appearance.models import AppearancePreferences
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.session import (
    SESSION_SNAPSHOT_SCHEMA_VERSION,
    SessionSnapshot,
)
from substitute.application.workspace_state import SnapshotCapturePort
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)

TResult = TypeVar("TResult")


def test_application_runtime_services_schedule_session_autosave_on_disk_lane(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runtime composition should route autosave persistence through execution."""

    app = _app()
    snapshot = _snapshot()
    repository = _SessionSnapshotRepository()
    submitter = _RecordingTaskSubmitter()
    execution_runtime = _ExecutionRuntime(submitter)
    single_shots: list[tuple[int, Callable[[], None]]] = []

    monkeypatch.setattr(runtime_module, "ExecutionRuntime", lambda: execution_runtime)
    monkeypatch.setattr(
        runtime_module,
        "SnapshotCaptureService",
        lambda: _SnapshotCaptureService(snapshot),
    )
    monkeypatch.setattr(
        runtime_module,
        "FileSessionSnapshotRepository",
        lambda _session_dir: repository,
    )
    monkeypatch.setattr(
        runtime_module,
        "FileRestoreProjectionCacheRepository",
        lambda _cache_dir: object(),
    )
    monkeypatch.setattr(
        "PySide6.QtCore.QTimer.singleShot",
        lambda delay_ms, callback: single_shots.append((delay_ms, callback)),
    )

    services = build_application_runtime_services(
        context=_context(tmp_path),
        comfy_output_stream=cast(TerminalOutputStream, object()),
        appearance_runtime=cast(AppearanceRuntimeController, _AppearanceRuntime()),
    )

    services.session_autosave_service.request_save(cast(SnapshotCapturePort, object()))
    app.processEvents()
    assert len(single_shots) == 1
    assert single_shots[0][0] == 500
    single_shots.pop()[1]()

    assert execution_runtime.submitter_calls == [
        {
            "name": "disk_io_low_priority",
            "owner_id": "session_autosave",
        }
    ]
    assert len(execution_runtime.dispatchers) == 1
    assert isinstance(execution_runtime.dispatchers[0], QtOwnerThreadDispatcher)
    assert len(submitter.requests) == 1
    request = submitter.requests[0]
    assert request.identity.request_id == 1
    assert request.identity.domain == "session_autosave_persistence"
    assert request.context.operation == "session_autosave_persistence"
    assert request.context.reason == "session_autosave"
    assert request.context.lane == "disk_io_low_priority"
    assert submitter.cancellations[0].is_cancelled is False

    request.work(submitter.cancellations[0])

    assert repository.saved == [snapshot]


def test_application_runtime_services_uses_shared_qt_execution_adapters() -> None:
    """Runtime composition should not own private Qt completion adapters."""

    source = Path(runtime_module.__file__).read_text(encoding="utf-8")

    assert "_QtSingleShotCompletionDispatcher" not in source
    assert "QTimer.singleShot" not in source
    assert "QtOwnerThreadDispatcher" in source
    assert "QtUiScheduler" in source


class _ExecutionRuntime:
    """Record process-runtime submitter creation."""

    def __init__(self, submitter: "_RecordingTaskSubmitter") -> None:
        """Store the submitter returned to composition."""

        self._submitter = submitter
        self.submitter_calls: list[dict[str, str]] = []
        self.dispatchers: list[object] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> "_RecordingTaskSubmitter":
        """Return the recording submitter for one owner lane."""

        self.submitter_calls.append({"name": name, "owner_id": owner_id})
        self.dispatchers.append(dispatcher)
        return self._submitter


class _RecordingTaskSubmitter:
    """Record submitted execution requests."""

    def __init__(self) -> None:
        """Initialize empty request storage."""

        self.requests: list[TaskRequest[object]] = []
        self.cancellations: list[CancellationToken] = []

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Record one task request without running it."""

        self.requests.append(cast(TaskRequest[object], request))
        self.cancellations.append(cancellation)
        return ManualTaskHandle(request)


class _SnapshotCaptureService:
    """Return a deterministic session snapshot."""

    def __init__(self, snapshot: SessionSnapshot) -> None:
        """Store the snapshot returned by capture."""

        self._snapshot = snapshot

    def capture(self, port: object) -> SessionSnapshot:
        """Return the stored snapshot."""

        del port
        return self._snapshot


class _SessionSnapshotRepository:
    """Record persisted session snapshots."""

    def __init__(self) -> None:
        """Initialize saved snapshot storage."""

        self.saved: list[SessionSnapshot] = []

    def load(self) -> SessionSnapshot | None:
        """Return no persisted session for this composition test."""

        return None

    def save(self, snapshot: SessionSnapshot) -> None:
        """Record one persisted session snapshot."""

        self.saved.append(snapshot)


class _AppearanceRuntime:
    """Return default appearance preferences for runtime composition."""

    def load_preferences(self) -> AppearancePreferences:
        """Return valid appearance preferences."""

        return default_appearance_preferences()


def _context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def _app() -> QApplication:
    """Return a QApplication for runtime Qt scheduling tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _snapshot() -> SessionSnapshot:
    """Build one deterministic session snapshot."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
        workspace=WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(),
            tab_order=(),
            active_route="",
            shell_layout=None,
        ),
    )
