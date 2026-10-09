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

"""Require explicit host initialization completion before endpoint publication."""

from __future__ import annotations

from itertools import permutations
from typing import Literal

import pytest

from substitute.app.bootstrap.shared_splash_host import _SplashHostReadiness


_PHASES: tuple[Literal["appearance", "runtime", "server"], ...] = (
    "appearance",
    "runtime",
    "server",
)


@pytest.mark.parametrize("phases", tuple(permutations(_PHASES)))
def test_ready_waits_for_all_initializers_in_any_callback_order(
    phases: tuple[Literal["appearance", "runtime", "server"], ...],
) -> None:
    """A missing or failed initializer cannot be hidden by Qt timer ordering."""
    published: list[bool] = []
    readiness = _SplashHostReadiness(lambda: published.append(True), lambda: None)
    for phase in phases[:-1]:
        readiness.complete(phase)
        readiness.complete(phase)
        assert published == []
    readiness.complete(phases[-1])
    assert published == [True]
    for phase in phases:
        readiness.complete(phase)
    assert published == [True]


@pytest.mark.parametrize("phase", ["appearance", "runtime"])
def test_initialization_failure_is_terminal_before_or_after_loop_entry(
    phase: Literal["appearance", "runtime"],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Exit once without advertising a broken host or leaking exception details."""
    published: list[bool] = []
    aborted: list[bool] = []
    readiness = _SplashHostReadiness(
        lambda: published.append(True), lambda: aborted.append(True)
    )
    readiness.fail(phase, RuntimeError("private-error-detail"))
    readiness.fail(phase, RuntimeError("again"))
    for completed in _PHASES:
        readiness.complete(completed)
    assert readiness.failed
    assert aborted == [True]
    assert published == []
    assert "error_type=RuntimeError" in caplog.text
    assert "private-error-detail" not in caplog.text


def test_cancelled_host_never_publishes_a_late_ready_message() -> None:
    """Keep a user cancellation authoritative while queued initializers drain."""
    published: list[bool] = []
    readiness = _SplashHostReadiness(lambda: published.append(True), lambda: None)
    readiness.cancel()
    for phase in _PHASES:
        readiness.complete(phase)
    assert not readiness.failed
    assert published == []


@pytest.mark.parametrize(
    "error", [BrokenPipeError("closed parent"), ValueError("closed stream")]
)
def test_ready_publication_failure_exits_instead_of_stranding_the_host(
    error: Exception,
) -> None:
    """A lost parent pipe is terminal even when initialization itself succeeded."""
    aborted: list[bool] = []
    attempts: list[bool] = []

    def publish() -> None:
        """Model one failed write or flush at the owned ready-pipe boundary."""
        attempts.append(True)
        raise error

    readiness = _SplashHostReadiness(publish, lambda: aborted.append(True))
    for phase in _PHASES:
        readiness.complete(phase)
    for phase in _PHASES:
        readiness.complete(phase)
    assert readiness.failed
    assert aborted == [True]
    assert attempts == [True]
