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

"""Import-boundary tests for titlebar generation control coordination."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generation_titlebar_control_registry_import_does_not_load_qfluentwidgets() -> (
    None
):
    """Importing registry coordination should not import concrete Fluent controls."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        importlib.import_module(
            "substitute.presentation.shell.generation_titlebar_control_registry"
        )
        loaded = any(
            name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
            for name in sys.modules
        )
        print(json.dumps(loaded))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "false"
