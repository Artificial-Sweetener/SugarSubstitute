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

"""Verify process handoff identity and PID-reuse protection."""

from __future__ import annotations

import os

import pytest

from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
    capture_process_identity,
    wait_for_process_exit,
)


def test_capture_process_identity_describes_current_process() -> None:
    """The live caller should expose a positive stable creation identity."""

    identity = capture_process_identity(os.getpid())

    assert identity.pid == os.getpid()
    assert identity.created_at > 0


@pytest.mark.parametrize(
    "created_at", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0]
)
def test_process_identity_rejects_invalid_creation_time(created_at: float) -> None:
    """Invalid comparison operands cannot become process ownership authority."""
    with pytest.raises(ValueError):
        ProcessIdentity(pid=123, created_at=created_at)


def test_wait_completes_when_original_identity_has_been_replaced() -> None:
    """A replacement process proves the outgoing incarnation has already exited."""

    identity = capture_process_identity(os.getpid())

    wait_for_process_exit(
        ProcessIdentity(identity.pid, identity.created_at - 100),
        timeout_seconds=0.01,
    )


def test_wait_times_out_for_matching_live_process() -> None:
    """A hung invoking process should produce a bounded actionable failure."""

    identity = capture_process_identity(os.getpid())

    with pytest.raises(ProcessIdentityError, match="Timed out"):
        wait_for_process_exit(identity, timeout_seconds=0.01)
