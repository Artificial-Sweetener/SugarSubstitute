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

"""Constrain handoff recovery to installation-owned caller roles."""

from pathlib import Path
import pytest
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.repair_handoff_process_scope import (
    RepairHandoffProcessScope,
)


@pytest.mark.parametrize(
    "role", ["venv", "base", "gui", "other-script", "other-root", "other-image"]
)
def test_handoff_scope_accepts_only_the_installed_caller(
    tmp_path: Path, role: str
) -> None:
    """Executable ownership and launch intent must agree before recovery may terminate."""
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    executable = layout.runtime_python
    arguments = [
        str(executable),
        str(layout.app_entrypoint),
        f"--install-root={layout.root}",
    ]
    if role == "base":
        executable = layout.runtime_dir / "python/cpython-fixture/python.exe"
        arguments[0] = str(executable)
    elif role == "gui":
        executable = layout.launcher_support_path / "LauncherUi.exe"
        arguments = [
            str(executable),
            "--launcher-ui-child",
            f"--install-root={layout.root}",
        ]
    elif role == "other-script":
        arguments[1] = str(tmp_path / "unrelated.py")
    elif role == "other-root":
        arguments[-1] = f"--install-root={tmp_path / 'other'}"
    elif role == "other-image":
        executable = tmp_path / "other/python.exe"
    scope = RepairHandoffProcessScope(layout)
    assert scope.accepts_invocation(executable, arguments, tmp_path) is (
        role in {"venv", "base", "gui"}
    )
