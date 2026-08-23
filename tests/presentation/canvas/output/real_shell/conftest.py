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

"""Own one exact real-shell Output harness lifetime per contract."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[RealShellOutputCanvasHarness]:
    """Create and synchronously destroy a real-shell Output canvas harness."""

    shell_harness = RealShellOutputCanvasHarness(output_root=tmp_path)
    try:
        yield shell_harness
    finally:
        shell_harness.close()
