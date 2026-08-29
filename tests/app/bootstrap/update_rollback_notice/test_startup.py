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

"""Verify deferred rolled-back update presentation after shell reveal."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackReportStore,
    UpdateRollbackStage,
)

from substitute.app.bootstrap.update_rollback_notice_startup import (
    schedule_update_rollback_notice_with_post_show_hydration,
)
from substitute.application.errors import ErrorReport, ErrorReportKind


class _ErrorPresenter:
    """Capture the shell-owned error report."""

    def __init__(self) -> None:
        """Create an empty presentation log."""

        self.reports: list[ErrorReport] = []

    def show_error_report(self, report: ErrorReport) -> None:
        """Record one modal report and emulate immediate dismissal."""

        self.reports.append(report)


class _MainWindow:
    """Expose the shell-owned error presenter expected by bootstrap."""

    def __init__(self) -> None:
        """Create the presentation surface."""

        self._error_presenter = _ErrorPresenter()


def test_update_rollback_notice_runs_after_reveal_and_acknowledges(
    tmp_path: Path,
) -> None:
    """Schedule the modal off the reveal stack and consume it after dismissal."""

    install_root = tmp_path / "install"
    store = UpdateRollbackReportStore(install_root)
    store.save(
        UpdateRollbackReport(
            attempted_version="0.21.3",
            stage=UpdateRollbackStage.CANDIDATE_READINESS,
            exception_type="ApplicationReadinessError",
            message="candidate did not become ready",
            traceback="ApplicationReadinessError: candidate did not become ready",
            occurred_at_utc="2026-08-29T02:09:03Z",
        )
    )
    shell_frame = object()
    main_window = _MainWindow()
    scheduled: list[Callable[[], None]] = []
    calls: list[str] = []

    def schedule(delay_ms: int, callback: Callable[[], None]) -> None:
        """Capture the required next-event-loop callback."""

        assert delay_ms == 0
        scheduled.append(callback)

    def schedule_hydration() -> str:
        """Record hydration scheduling and return its startup handle."""

        calls.append("hydrate")
        return "hydration-started"

    hydration_result = schedule_update_rollback_notice_with_post_show_hydration(
        schedule_hydration=schedule_hydration,
        install_root=install_root,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda candidate: (
            main_window if candidate is shell_frame else object()
        ),
        scheduler=schedule,
    )

    assert hydration_result == "hydration-started"
    assert calls == ["hydrate"]
    assert main_window._error_presenter.reports == []
    assert len(scheduled) == 1

    scheduled[0]()

    assert len(main_window._error_presenter.reports) == 1
    assert (
        main_window._error_presenter.reports[0].kind
        is ErrorReportKind.SUBSTITUTE_INTERNAL
    )
    assert store.load() is None
