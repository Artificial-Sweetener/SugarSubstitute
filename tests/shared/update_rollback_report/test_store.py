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

"""Verify durable launcher-to-application rollback-report handoff."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReport,
    UpdateRollbackReportStore,
    UpdateRollbackStage,
)


def test_update_rollback_report_store_round_trips_and_acknowledges(
    tmp_path: Path,
) -> None:
    """Persist exact bounded diagnostics until the restored app acknowledges them."""

    store = UpdateRollbackReportStore(tmp_path / "install")
    report = UpdateRollbackReport.capture(
        attempted_version="0.21.3",
        stage=UpdateRollbackStage.CANDIDATE_READINESS,
        error=RuntimeError("candidate did not become ready"),
        now=datetime(2026, 8, 29, 2, 9, 3, tzinfo=UTC),
    )

    store.save(report)

    assert store.load() == report
    assert report.occurred_at_utc == "2026-08-29T02:09:03Z"
    assert "RuntimeError: candidate did not become ready" in report.traceback

    store.acknowledge()

    assert store.load() is None
