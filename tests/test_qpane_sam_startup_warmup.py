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

from pathlib import Path

import pytest

from tests.execution_testing import ImmediateTaskSubmitter
from substitute.app.bootstrap.cutecanvas_sam_startup_warmup import (
    CuteCanvasSamStartupWarmupHandle,
    cutecanvas_sam_warmup_snapshot,
    reset_cutecanvas_sam_warmup_snapshot_for_tests,
)
from substitute.shared.cutecanvas_sam_warmup_state import (
    cutecanvas_sam_warmup_is_terminal,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative_path",
    (
        Path("tests/conftest.py"),
        Path(".github/workflows/tests.yml"),
        Path(".github/workflows/comfy-compatibility.yml"),
    ),
)
def test_test_runners_disable_only_the_default_cutecanvas_sam_warmup(
    relative_path: Path,
) -> None:
    """Test runners must use the production warmup guard's current identity."""

    content = (_REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    assert "SUBSTITUTE_DISABLE_CUTECANVAS_SAM_WARMUP" in content
    assert "SUBSTITUTE_DISABLE_QPANE_SAM_WARMUP" not in content


def test_cutecanvas_sam_warmup_records_completed_state() -> None:
    """Successful warmup should publish completed state without blocking callers."""

    reset_cutecanvas_sam_warmup_snapshot_for_tests()
    calls: list[str] = []
    handle = CuteCanvasSamStartupWarmupHandle(
        submitter=ImmediateTaskSubmitter(),
        ensure_dependencies=lambda: calls.append("ensure"),
    )
    assert not cutecanvas_sam_warmup_is_terminal()

    handle.start()

    snapshot = cutecanvas_sam_warmup_snapshot()
    assert calls == ["ensure"]
    assert snapshot.state == "completed"
    assert snapshot.elapsed_ms is not None
    assert cutecanvas_sam_warmup_is_terminal()


def test_cutecanvas_sam_warmup_failure_is_best_effort() -> None:
    """Warmup dependency failures should be recorded without escaping startup."""

    reset_cutecanvas_sam_warmup_snapshot_for_tests()

    def fail() -> None:
        """Raise one deterministic dependency failure."""

        raise RuntimeError("missing dependency")

    handle = CuteCanvasSamStartupWarmupHandle(
        submitter=ImmediateTaskSubmitter(),
        ensure_dependencies=fail,
    )

    handle.start()

    snapshot = cutecanvas_sam_warmup_snapshot()
    assert snapshot.state == "failed"
    assert "missing dependency" in snapshot.error
    assert cutecanvas_sam_warmup_is_terminal()


def test_default_cutecanvas_sam_warmup_can_be_disabled_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests should disable default Torch/SAM imports without disabling fakes."""

    reset_cutecanvas_sam_warmup_snapshot_for_tests()
    monkeypatch.setenv("SUBSTITUTE_DISABLE_CUTECANVAS_SAM_WARMUP", "1")
    handle = CuteCanvasSamStartupWarmupHandle(submitter=ImmediateTaskSubmitter())

    handle.start()

    snapshot = cutecanvas_sam_warmup_snapshot()
    assert snapshot.state == "disabled"
    assert cutecanvas_sam_warmup_is_terminal()
