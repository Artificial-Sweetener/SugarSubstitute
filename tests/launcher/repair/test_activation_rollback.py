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

"""Keep application repair and launcher activation in one recovery boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from .execution_support import (
    _RuntimeProvisioner,
    _prepared_request,
    _write_old_install,
    _write_launcher,
)


@pytest.mark.parametrize("previous_generation", [False, True])
def test_selection_write_failure_restores_application(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    previous_generation: bool,
) -> None:
    """Restore the previous app when its matching launcher cannot become active."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)
    selection = LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE)
    if previous_generation:
        prior = layout.launcher_dir / "updates" / "prior"
        _write_launcher(prior)
        selection.activate(selection.publish(prior, version="0.9.0"))
    previous_launcher = selection.resolve()
    version_path = layout.app_dir / "substitute" / "_version.py"
    previous = version_path.read_bytes()
    selection_path = LauncherBundlePaths(layout.root).selection
    replace = Path.replace
    failure_injected = False

    def reject_selection(source: Path, target: str | Path) -> Path:
        """Deny only the candidate's final selection rename."""
        nonlocal failure_injected
        if not failure_injected and Path(target).resolve() == selection_path.resolve():
            failure_injected = True
            raise PermissionError("injected selection write failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", reject_selection)
    with pytest.raises((OSError, RuntimeError)):
        RepairExecutionService(
            runtime_provisioner=_RuntimeProvisioner()
        ).execute_application(request)
    assert version_path.read_bytes() == previous
    assert layout.runtime_python.read_bytes() == b"old-python"
    assert layout.executable_path.read_bytes() == b"old-launcher"
    assert failure_injected
    assert selection.resolve() == previous_launcher
    assert not (layout.root / ".repair" / "pending.json").exists()
