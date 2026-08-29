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

"""Test Windows managed Comfy launch event-loop policy."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_launch_command import (
    build_managed_launch_command,
)
from substitute.infrastructure.process.hidden_process_runner import run_command

pytestmark = pytest.mark.platforms("windows")


def test_windows_managed_comfy_uses_selector_event_loop_policy(
    tmp_path: Path,
) -> None:
    """Managed Comfy should absorb peer resets without Proactor tracebacks."""

    workspace = tmp_path / "comfyui"
    workspace.mkdir()
    (workspace / "main.py").write_text(
        "import asyncio\n"
        "from pathlib import Path\n"
        "Path('event-loop-policy.txt').write_text(\n"
        "    type(asyncio.get_event_loop_policy()).__name__,\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )
    command = build_managed_launch_command(
        venv_python=Path(sys.executable),
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=workspace,
        manager_runtime=ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=Path(sys.executable),
        ),
        force_cpu_mode=False,
    )

    assert command[1] == "-c"
    assert "WindowsSelectorEventLoopPolicy" in command[2]
    assert command[3:5] == (str(workspace), str(workspace / "main.py"))
    assert command[5:] == (
        "--listen",
        "127.0.0.1",
        "--port",
        "8188",
        "--enable-manager",
    )

    result = run_command(command, cwd=workspace, check=True)

    assert result.returncode == 0
    assert (workspace / "event-loop-policy.txt").read_text(encoding="utf-8") == (
        "WindowsSelectorEventLoopPolicy"
    )
