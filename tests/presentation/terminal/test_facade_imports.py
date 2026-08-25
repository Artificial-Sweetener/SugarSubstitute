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

"""Tests for shared terminal package import boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

_PROBE_PREFIX = "SUGARSUBSTITUTE_IMPORT_PROBE="


def test_terminal_stream_import_does_not_import_output_view() -> None:
    """Importing the stream should not import the widget view facade."""

    result = _run_import_probe(
        """import json
import sys
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
print("SUGARSUBSTITUTE_IMPORT_PROBE=" + json.dumps({
    "class_name": TerminalOutputStream.__name__,
    "view_loaded": (
        "sugarsubstitute_shared.presentation.terminal.output_view" in sys.modules
    ),
}))
"""
    )

    assert result == {"class_name": "TerminalOutputStream", "view_loaded": False}


def test_terminal_facade_resolves_output_view_lazily() -> None:
    """The package facade should still expose the terminal view on demand."""

    result = _run_import_probe(
        """import json
import sys
import sugarsubstitute_shared.presentation.terminal as facade
view_module = "sugarsubstitute_shared.presentation.terminal.output_view"
stream_name = facade.TerminalOutputStream.__name__
before = view_module in sys.modules
view_name = facade.TerminalOutputView.__name__
print("SUGARSUBSTITUTE_IMPORT_PROBE=" + json.dumps({
    "stream_name": stream_name,
    "view_loaded_before": before,
    "view_name": view_name,
    "view_loaded_after": view_module in sys.modules,
}))
"""
    )

    assert result == {
        "stream_name": "TerminalOutputStream",
        "view_loaded_before": False,
        "view_name": "TerminalOutputView",
        "view_loaded_after": True,
    }


def _run_import_probe(script: str) -> dict[str, object]:
    """Execute one import-boundary probe in a clean bounded interpreter."""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    result_line = next(
        line
        for line in reversed(completed.stdout.splitlines())
        if line.startswith(_PROBE_PREFIX)
    )
    return cast(
        dict[str, object],
        json.loads(result_line.removeprefix(_PROBE_PREFIX)),
    )
