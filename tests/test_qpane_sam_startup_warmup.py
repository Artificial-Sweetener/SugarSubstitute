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

"""Tests for launch-splash QPane SAM dependency warmup."""

from __future__ import annotations

import pytest

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.app.bootstrap.qpane_sam_startup_warmup import (
    QPaneSamStartupWarmupHandle,
    qpane_sam_warmup_snapshot,
    reset_qpane_sam_warmup_snapshot_for_tests,
)


def test_qpane_sam_warmup_records_completed_state() -> None:
    """Successful warmup should publish completed state without blocking callers."""

    reset_qpane_sam_warmup_snapshot_for_tests()
    calls: list[str] = []
    handle = QPaneSamStartupWarmupHandle(
        submitter=ImmediateTaskSubmitter(),
        ensure_dependencies=lambda: calls.append("ensure"),
    )

    handle.start()

    snapshot = qpane_sam_warmup_snapshot()
    assert calls == ["ensure"]
    assert snapshot.state == "completed"
    assert snapshot.elapsed_ms is not None


def test_qpane_sam_warmup_failure_is_best_effort() -> None:
    """Warmup dependency failures should be recorded without escaping startup."""

    reset_qpane_sam_warmup_snapshot_for_tests()

    def fail() -> None:
        """Raise one deterministic dependency failure."""

        raise RuntimeError("missing dependency")

    handle = QPaneSamStartupWarmupHandle(
        submitter=ImmediateTaskSubmitter(),
        ensure_dependencies=fail,
    )

    handle.start()

    snapshot = qpane_sam_warmup_snapshot()
    assert snapshot.state == "failed"
    assert "missing dependency" in snapshot.error


def test_default_qpane_sam_warmup_can_be_disabled_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests should disable default Torch/SAM imports without disabling fakes."""

    reset_qpane_sam_warmup_snapshot_for_tests()
    monkeypatch.setenv("SUBSTITUTE_DISABLE_QPANE_SAM_WARMUP", "1")
    handle = QPaneSamStartupWarmupHandle(submitter=ImmediateTaskSubmitter())

    handle.start()

    snapshot = qpane_sam_warmup_snapshot()
    assert snapshot.state == "disabled"
