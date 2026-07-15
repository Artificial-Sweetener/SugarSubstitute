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

"""Tests for startup phase timing diagnostics."""

from __future__ import annotations

import logging

import pytest

from substitute.app.bootstrap.startup_timing import (
    StartupTimer,
    StartupTimingRecord,
)


def test_startup_timer_records_phase_duration() -> None:
    """Startup timer should preserve completed phase records in order."""

    ticks = iter((0.0, 1.0, 1.125, 2.0, 2.050))
    timer = StartupTimer(clock=lambda: next(ticks))

    with timer.phase("startup.first"):
        pass
    with timer.phase("startup.second"):
        pass

    first, second = timer.records()
    assert first == StartupTimingRecord(phase="startup.first", elapsed_ms=125.0)
    assert second.phase == "startup.second"
    assert second.elapsed_ms == pytest.approx(50.0)


def test_startup_timer_logs_completed_phase(caplog: pytest.LogCaptureFixture) -> None:
    """Startup timer should emit structured diagnostics for each completed phase."""

    ticks = iter((0.0, 3.0, 3.010))
    timer = StartupTimer(clock=lambda: next(ticks))

    with caplog.at_level(logging.INFO):
        with timer.phase("startup.logged"):
            pass

    assert "Startup phase completed" in caplog.text
    assert "phase=startup.logged" in caplog.text
    assert "elapsed_ms=10.000" in caplog.text


def test_startup_timer_records_milestones() -> None:
    """Startup timer should expose named process-relative milestones."""

    ticks = iter((10.0, 10.100, 10.450))
    timer = StartupTimer(clock=lambda: next(ticks))

    first = timer.mark("splash_closed")
    second = timer.mark("hydration_completed")

    assert first.name == "splash_closed"
    assert first.elapsed_ms == pytest.approx(100.0)
    assert second.elapsed_ms == pytest.approx(450.0)
    assert timer.milestones() == (first, second)
    assert timer.elapsed_ms_for_milestone("splash_closed") == pytest.approx(100.0)
    assert timer.elapsed_ms_between(
        "splash_closed",
        "hydration_completed",
    ) == pytest.approx(350.0)
    assert timer.elapsed_ms_between("missing", "hydration_completed") is None
