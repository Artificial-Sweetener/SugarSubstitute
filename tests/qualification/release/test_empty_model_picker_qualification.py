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

"""Keep the release model-picker qualification aligned with production flows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_empty_model_picker_qualification_runs_to_completion(tmp_path: Path) -> None:
    """Exercise both public and key-backed paths in the release subprocess."""

    repository_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONPATH"] = str(repository_root)
    result = subprocess.run(
        [sys.executable, "-m", "tools.qualify_empty_model_picker"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(
        (
            tmp_path
            / "build/qualification/empty-model-picker/empty-model-picker-qualification.json"
        ).read_text(encoding="utf-8")
    )
    assert report["result"] == "passed"
    assert report["public_flow"]["credential_prompts_after_selection"] == 0
    assert report["protected_flow"]["credential_prompts_after_selection"] == 1
