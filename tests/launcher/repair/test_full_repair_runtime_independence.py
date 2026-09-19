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

"""Verify complete runtime replacement is independent of the broken old runtime."""

from pathlib import Path
import json

from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
    RepairScope,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from tests.launcher.repair.execution_support import (
    _ManagedComfyRepairer,
    _RuntimeProvisioner,
    _prepared_request,
    _write_old_install,
)


class _UnusableCurrentRuntime(_ManagedComfyRepairer):
    """Reject maintenance that needs the interpreter being replaced."""

    def repair_owned_nodes(
        self, *, layout: InstallLayout, ownership: ManagedComfyOwnership
    ) -> None:
        """Represent the real subprocess error from a broken current interpreter."""
        raise RuntimeError("Existing Comfy interpreter cannot execute")

    def validate_owned_nodes(
        self, *, layout: InstallLayout, ownership: ManagedComfyOwnership
    ) -> None:
        """Reject validation of the old runtime before complete replacement."""
        raise RuntimeError("Existing Comfy interpreter cannot execute")


def test_full_repair_rebuilds_without_invoking_broken_current_runtime(
    tmp_path: Path,
) -> None:
    """Full repair must reach replacement when current runtime maintenance is impossible."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    workspace = layout.root / "comfyui"
    settings = layout.user_dir / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "comfy_target.json").write_text(
        json.dumps(
            {
                "mode": "managed_local",
                "workspace_path": str(workspace),
                "install_owned": True,
            }
        ),
        encoding="utf-8",
    )
    (workspace / "main.py").write_text("broken old runtime", encoding="utf-8")
    protected = workspace / "custom_nodes" / "third-party" / "node.py"
    before = protected.read_bytes()
    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        comfy_repairer=_UnusableCurrentRuntime(),
    ).execute_application(
        _prepared_request(layout, scope=RepairScope.FULL_MANAGED_COMFY)
    )

    assert result.repaired_managed_comfy_nodes
    assert result.comfy_quarantine_root is not None
    assert (workspace / "main.py").read_text(encoding="utf-8") == "fresh-core"
    assert (
        workspace / ".venv" / "Scripts" / "python.exe"
    ).read_bytes() == b"fresh-final"
    assert protected.read_bytes() == before
