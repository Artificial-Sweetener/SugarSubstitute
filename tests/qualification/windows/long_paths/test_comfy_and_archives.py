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

"""Qualify managed Comfy and archive extraction at long Windows paths."""

from __future__ import annotations

from pathlib import Path
import sys
import zipfile


from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_launch_command import (
    build_managed_launch_command,
)
from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    NativeSevenZipExtractionProcess,
)
from sugarsubstitute_shared.windows_long_paths import (
    operational_path,
)
from substitute.infrastructure.process.hidden_process_runner import run_command
from substitute.infrastructure.filesystem import remove_app_owned_path


def test_managed_comfy_bootstrap_enters_long_workspace(tmp_path: Path) -> None:
    """The controlled Python bootstrap should restore Comfy's workspace semantics."""

    workspace = operational_path(tmp_path / "comfy")
    while len(str(workspace)) < 285:
        workspace /= "segment-0123456789abcdef"
    workspace.mkdir(parents=True)
    main_path = workspace / "main.py"
    main_path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path('cwd-proof.txt').write_text('|'.join(sys.argv[1:]), encoding='utf-8')\n",
        encoding="utf-8",
    )
    command = build_managed_launch_command(
        venv_python=Path(sys.executable),
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=workspace,
        manager_runtime=ComfyManagerRuntime(
            kind=ComfyManagerKind.LEGACY_CUSTOM_NODE,
            workspace=workspace,
            python_executable=Path(sys.executable),
        ),
        force_cpu_mode=False,
    )

    result = run_command(command, cwd=workspace, check=True)

    assert result.returncode == 0
    assert (workspace / "cwd-proof.txt").read_text(encoding="utf-8") == (
        "--listen|127.0.0.1|--port|8188"
    )


def test_native_seven_zip_extracts_to_long_destination(tmp_path: Path) -> None:
    """Bundled 7-Zip should accept extended archive and destination arguments."""

    archive_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/proof.txt", "7zip proof")
    target_root = operational_path(tmp_path / "seven-zip-target")
    target = target_root
    while len(str(target)) < 285:
        target /= "segment-0123456789abcdef"
    target.mkdir(parents=True)

    try:
        process = NativeSevenZipExtractionProcess(timeout_seconds=30)
        process.extract(archive_path, target)

        assert (target / "nested" / "proof.txt").read_text(encoding="utf-8") == (
            "7zip proof"
        )
    finally:
        remove_app_owned_path(target_root)
