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

"""Import-boundary tests for application icon resources."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_application_icon_import_does_not_load_qfluentwidgets() -> None:
    """Importing Qt app-icon helpers should not load the Fluent widget package."""

    code = textwrap.dedent(
        """
        import importlib
        import json
        import sys

        module = importlib.import_module("substitute.presentation.resources.app_icon")
        getattr(module, "application_icon")
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


def test_app_icon_export_still_resolves_fluent_icon_enum() -> None:
    """Legacy AppIcon imports should still return the qfluent-compatible enum."""

    code = textwrap.dedent(
        """
        import json
        import sys

        from substitute.presentation.resources.app_icon import AppIcon

        loaded = any(
            name == "qfluentwidgets" or name.startswith("qfluentwidgets.")
            for name in sys.modules
        )
        print(json.dumps({"loaded": loaded, "value": AppIcon.CUBE_20_FILLED.value}))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == '{"loaded": true, "value": "Cube20Filled"}'
