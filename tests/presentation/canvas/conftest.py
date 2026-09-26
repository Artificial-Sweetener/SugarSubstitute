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

"""Own complete CuteCanvas execution for presentation tests."""

from __future__ import annotations

from collections.abc import Iterator

import psutil  # type: ignore[import-untyped]
import pytest
from cutecanvas import ExecutionRuntime
from qpane import create_default_execution_runtime


_DETERMINISTIC_TOTAL_MEMORY_BYTES = 2 * 1024**3
_DETERMINISTIC_AVAILABLE_MEMORY_BYTES = 1024**3


@pytest.fixture(autouse=True)
def deterministic_canvas_cache_headroom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep QPane auto-cache budgets independent of concurrent host memory use."""

    memory = psutil.virtual_memory()._replace(
        total=_DETERMINISTIC_TOTAL_MEMORY_BYTES,
        available=_DETERMINISTIC_AVAILABLE_MEMORY_BYTES,
    )
    monkeypatch.setattr(psutil, "virtual_memory", lambda: memory)


@pytest.fixture
def execution_runtime() -> Iterator[ExecutionRuntime]:
    """Provide one explicitly owned default runtime per canvas test."""

    runtime = create_default_execution_runtime()
    try:
        yield runtime
    finally:
        runtime.shutdown(wait=True)
