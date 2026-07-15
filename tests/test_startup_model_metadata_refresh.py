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

"""Tests for startup model metadata refresh coordination."""

from __future__ import annotations

from tests.execution_testing import (
    ImmediateTaskSubmitter,
    QueuedTaskSubmitter,
)
from substitute.app.bootstrap.model_metadata_refresh import (
    StartupModelMetadataRefreshHandle,
)
from substitute.application.model_metadata import (
    ModelMetadataProgressSink,
    RefreshCancellationToken,
)


class _FakeProgressSink:
    """Collect startup metadata refresh output."""

    def __init__(self) -> None:
        self.records: list[str] = []

    def emit_line(self, line: str) -> None:
        """Record one stable line."""

        self.records.append(line)

    def emit_progress(self, line: str) -> None:
        """Record one transient line."""

        self.records.append(line)


class _FakeService:
    """Record refresh invocations from the startup handle."""

    def __init__(self) -> None:
        self.calls = 0

    def refresh(
        self,
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken | None = None,
    ) -> None:
        """Record refresh execution."""

        _ = cancellation_token
        self.calls += 1
        progress.emit_line("Model metadata: complete.")


def test_startup_refresh_handle_releases_splash_when_refresh_finishes() -> None:
    """Startup refresh handle should release splash after immediate completion."""

    service = _FakeService()
    progress = _FakeProgressSink()
    finished: list[str] = []
    handle = StartupModelMetadataRefreshHandle(
        service_factory=lambda: service,
        progress_sink=progress,
        submitter=ImmediateTaskSubmitter(),
        monotonic=lambda: 10.0,
        finished_callback=lambda: finished.append("done"),
    )

    handle.start()

    assert service.calls == 1
    assert handle.ready_to_release_splash() is True
    assert progress.records == ["Model metadata: complete."]
    assert finished == ["done"]


def test_startup_refresh_handle_releases_splash_after_budget() -> None:
    """Startup refresh handle should release splash when the startup budget expires."""

    current_time = 10.0
    submitter = QueuedTaskSubmitter()
    closed: list[str] = []
    handle = StartupModelMetadataRefreshHandle(
        service_factory=_FakeService,
        progress_sink=_FakeProgressSink(),
        submitter=submitter,
        startup_budget_seconds=15.0,
        close_submitter=lambda: closed.append("closed"),
        monotonic=lambda: current_time,
    )

    handle.start()
    assert len(submitter.handles) == 1
    assert handle.ready_to_release_splash() is False
    current_time = 25.0
    assert handle.ready_to_release_splash() is True
    handle.shutdown()
    assert closed == ["closed"]
