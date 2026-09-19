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

"""Keep selected launcher dependencies separate from persistent installation paths."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_process_discovery import (
    InstalledInvocationScope,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.launcher_ui_process import (
    build_launcher_ui_command,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import _write_bundle_tree, _write_installed_layout


@pytest.mark.parametrize(
    "role",
    ["SugarSubstitute.exe", "launcher-bin/Repair.exe", "launcher-bin/LauncherUi.exe"],
)
def test_generation_process_uses_its_own_ui_and_installation_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    """Use matching bundle dependencies without relocating user or runtime state."""
    root = _write_installed_layout(tmp_path / "installation")
    source = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(source, marker="candidate")
    selected = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).publish(
        source, version="1"
    )
    executable = selected.root / role
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(
        sys, "_MEIPASS", str(selected.root / "launcher-bin"), raising=False
    )
    layout = InstallLayout.from_root(root, target=WINDOWS_X64)
    assert layout.root == root
    assert layout.executable_path == root / "SugarSubstitute.exe"
    assert layout.app_dir == root / "app"
    assert layout.runtime_dir == root / "runtime"
    assert layout.launcher_support_path == selected.root / "launcher-bin"
    command = build_launcher_ui_command(
        layout, ("--launcher-ui-child", f"--install-root={root}")
    )
    assert Path(command[0]).samefile(selected.root / "launcher-bin" / "LauncherUi.exe")


@pytest.mark.parametrize("role", ["SugarSubstitute.exe", "launcher-bin/Repair.exe"])
def test_recovery_accepts_verified_generation_owner(tmp_path: Path, role: str) -> None:
    """Recover an older sealed generation even after activation has moved onward."""
    root = _write_installed_layout(tmp_path / "installation")
    source = root / "launcher" / "updates" / "staged"
    _write_bundle_tree(source, marker="candidate")
    selected = LauncherBundleSelection(root, WINDOWS_X64_BUNDLE).publish(
        source, version="1"
    )
    image = selected.root / role
    scope = InstalledInvocationScope(InstallLayout.from_root(root, target=WINDOWS_X64))
    assert scope.accepts_invocation(image, (str(image), f"--install-root={root}"), root)
    assert not scope.accepts_invocation(
        image, (str(image), f"--install-root={tmp_path / 'other'}"), root
    )
    assert not scope.accepts_invocation(
        image, (str(image), "--launcher-ui-child"), root
    )
    (selected.root.parent / "bundle.json").unlink()
    assert scope.accepts_invocation(image, (str(image), f"--install-root={root}"), root)


@pytest.mark.parametrize(
    "relative",
    [
        "launcher/bundles/not-a-generation/payload/SugarSubstitute.exe",
        "launcher/bundles/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SugarSubstitute.exe",
        "launcher/bundles/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/payload/launcher-bin/LauncherUi.exe",
        "launcher/updates/staged/SugarSubstitute.exe",
    ],
)
def test_recovery_rejects_unowned_generation_roles(
    tmp_path: Path, relative: str
) -> None:
    """Reject arbitrary staging, malformed namespaces and Qt helper roles."""
    root = tmp_path / "installation"
    scope = InstalledInvocationScope(InstallLayout.from_root(root, target=WINDOWS_X64))
    image = root / relative
    assert not scope.accepts_invocation(
        image, (str(image), f"--install-root={root}"), root
    )
