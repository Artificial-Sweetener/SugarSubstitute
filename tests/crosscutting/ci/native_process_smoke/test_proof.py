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

"""Tests for bounded native GUI process smoke proofs."""

from __future__ import annotations

import sys

import pytest

from tools.ci.native_process_smoke import (
    NativeProcessSmokeError,
    prove_process_stays_alive,
)


def test_native_process_smoke_accepts_long_running_process() -> None:
    """A process that survives the observation interval passes."""

    prove_process_stays_alive(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        duration_seconds=0.05,
    )


def test_native_process_smoke_reports_early_exit_output() -> None:
    """An early process exit reports its code and captured diagnostics."""

    with pytest.raises(NativeProcessSmokeError, match="native failure"):
        prove_process_stays_alive(
            [sys.executable, "-c", "print('native failure')"],
            duration_seconds=10.0,
        )
