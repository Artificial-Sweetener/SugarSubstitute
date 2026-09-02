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

"""Verify exact application repair execution, preservation, and rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair import (
    ManagedComfyOwnership,
    PreparedRepairRequest,
    RepairExecutionService,
    RepairScope,
    directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningResult


class _RuntimeProvisioner:
    """Create a deterministic runtime candidate without subprocesses or downloads."""

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Materialize the expected Python and return its typed outcome."""

        layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
        layout.runtime_python.write_bytes(b"candidate-python")
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=layout.app_dir / "requirements.txt",
        )


class _RejectingStateWriter:
    """Inject final validation failure after all candidate components exist."""

    def write(self, *, layout: InstallLayout, request: PreparedRepairRequest) -> None:
        """Create representative candidate launcher state."""

        del request
        layout.state_path.parent.mkdir(parents=True, exist_ok=True)
        layout.state_path.write_text("candidate", encoding="utf-8")

    def validate(
        self, *, layout: InstallLayout, request: PreparedRepairRequest
    ) -> None:
        """Reject the candidate after observing its active location."""

        del layout, request
        raise RuntimeError("injected final validation failure")


class _ManagedComfyRepairer:
    """Restore exact representative owned nodes without network or subprocesses."""

    def repair_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Create both transaction-owned nodepack candidates."""

        assert ownership.workspace_root == layout.root / "comfyui"
        custom_nodes = layout.root / "comfyui" / "custom_nodes"
        for name in ("substitute-backend", "SugarCubes"):
            path = custom_nodes / name
            path.mkdir(parents=True)
            (path / "version.txt").write_text("new-owned", encoding="utf-8")

    def validate_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Require both candidates to exist after repair."""

        assert ownership.install_owned
        for name in ("substitute-backend", "SugarCubes"):
            assert (
                layout.root / "comfyui" / "custom_nodes" / name / "version.txt"
            ).read_text(encoding="utf-8") == "new-owned"

    def stage_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
        destination: Path,
    ) -> None:
        """Create fresh core, environment, and exact owned-node candidates."""

        assert ownership.workspace_root == layout.root / "comfyui"
        (destination / "main.py").parent.mkdir(parents=True, exist_ok=True)
        (destination / "main.py").write_text("fresh-core", encoding="utf-8")
        (destination / ".venv" / "Scripts").mkdir(parents=True)
        (destination / ".venv" / "Scripts" / "python.exe").write_bytes(b"fresh")
        for name in ("substitute-backend", "SugarCubes"):
            node = destination / "custom_nodes" / name
            node.mkdir(parents=True)
            (node / "version.txt").write_text("full-owned", encoding="utf-8")

    def validate_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Require fresh core/runtime and both owned packages after promotion."""

        assert ownership.workspace_root == layout.root / "comfyui"
        workspace = layout.root / "comfyui"
        assert (workspace / "main.py").read_text(encoding="utf-8") == "fresh-core"
        assert (workspace / ".venv" / "Scripts" / "python.exe").is_file()
        for name in ("substitute-backend", "SugarCubes"):
            assert (workspace / "custom_nodes" / name / "version.txt").read_text(
                encoding="utf-8"
            ) == "full-owned"


def _write_app(path: Path, version: str) -> None:
    """Create one structurally valid app payload with literal version metadata."""

    (path / "substitute").mkdir(parents=True)
    (path / "third_party").mkdir()
    (path / "main.py").write_text("", encoding="utf-8")
    (path / "requirements.txt").write_text("", encoding="utf-8")
    (path / "sitecustomize.py").write_text("", encoding="utf-8")
    (path / "substitute" / "_version.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )


def _write_launcher(path: Path) -> None:
    """Create a valid Windows launcher bundle including adjacent repair entrypoint."""

    path.mkdir(parents=True)
    (path / "SugarSubstitute.exe").write_bytes(b"new-launcher")
    (path / "launcher-bin").mkdir()
    (path / "launcher-bin" / "LauncherUi.exe").write_bytes(b"new-launcher-ui")
    (path / "launcher-bin" / "Repair.exe").write_bytes(b"new-repair")
    (path / "launcher-bin" / "runtime.dll").write_bytes(b"new-support")


def _prepared_request(
    layout: InstallLayout,
    *,
    version: str = "1.2.3",
    scope: RepairScope = RepairScope.APPLICATION,
) -> PreparedRepairRequest:
    """Stage a complete application and launcher candidate under repair ownership."""

    staging = layout.root / ".repair" / "staging" / version
    app = staging / "app"
    launcher = staging / "launcher"
    _write_app(app, version)
    _write_launcher(launcher)
    return PreparedRepairRequest(
        install_root=layout.root,
        scope=scope,
        version=version,
        channel="stable",
        target_key=WINDOWS_X64.key,
        staged_app_dir=app,
        staged_launcher_dir=launcher,
        staged_app_sha256=directory_tree_sha256(app),
        staged_launcher_sha256=directory_tree_sha256(launcher),
    )


def _write_old_install(layout: InstallLayout) -> None:
    """Create replaceable components and protected data with distinct bytes."""

    _write_app(layout.app_dir, "0.9.0")
    layout.runtime_python.parent.mkdir(parents=True)
    layout.runtime_python.write_bytes(b"old-python")
    layout.executable_path.parent.mkdir(parents=True, exist_ok=True)
    layout.executable_path.write_bytes(b"old-launcher")
    layout.launcher_support_path.mkdir()
    (layout.launcher_support_path / "LauncherUi.exe").write_bytes(b"old-launcher-ui")
    (layout.launcher_support_path / "Repair.exe").write_bytes(b"old-repair")
    (layout.launcher_support_path / "runtime.dll").write_bytes(b"old-support")
    protected = (
        layout.user_dir / "projects" / "work.json",
        layout.appdata_dir / "session" / "autosave.json",
        layout.root / "comfyui" / "models" / "model.safetensors",
        layout.root / "comfyui" / "custom_nodes" / "third-party" / "node.py",
    )
    for index, path in enumerate(protected):
        path.parent.mkdir(parents=True)
        path.write_bytes(f"protected-{index}".encode())


def test_execution_commits_exact_version_and_preserves_all_user_comfy_data(
    tmp_path: Path,
) -> None:
    """A standard repair should replace product components and retain protected bytes."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    protected_paths = (
        layout.user_dir / "projects" / "work.json",
        layout.appdata_dir / "session" / "autosave.json",
        layout.root / "comfyui" / "models" / "model.safetensors",
        layout.root / "comfyui" / "custom_nodes" / "third-party" / "node.py",
    )
    before = {path: path.read_bytes() for path in protected_paths}
    request = _prepared_request(layout)

    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner()
    ).execute_application(request)

    assert result.version == "1.2.3"
    assert not result.repaired_managed_comfy_nodes
    assert (layout.app_dir / "substitute" / "_version.py").read_text(
        encoding="utf-8"
    ) == '__version__ = "1.2.3"\n'
    assert layout.runtime_python.read_bytes() == b"candidate-python"
    assert layout.executable_path.read_bytes() == b"new-launcher"
    assert (
        layout.launcher_support_path / "LauncherUi.exe"
    ).read_bytes() == b"new-launcher-ui"
    assert (layout.launcher_support_path / "Repair.exe").read_bytes() == b"new-repair"
    assert {path: path.read_bytes() for path in protected_paths} == before


def test_execution_rejects_tampered_staging_before_active_mutation(
    tmp_path: Path,
) -> None:
    """A changed staged file should stop before any installed component moves."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)
    request.staged_app_dir.joinpath("main.py").write_text("tampered", encoding="utf-8")
    old_app = (layout.app_dir / "substitute" / "_version.py").read_bytes()

    with pytest.raises(RuntimeError, match="integrity mismatch"):
        RepairExecutionService(
            runtime_provisioner=_RuntimeProvisioner()
        ).execute_application(request)

    assert (layout.app_dir / "substitute" / "_version.py").read_bytes() == old_app
    assert layout.runtime_python.read_bytes() == b"old-python"
    assert layout.executable_path.read_bytes() == b"old-launcher"


def test_execution_rolls_back_every_component_after_final_validation_failure(
    tmp_path: Path,
) -> None:
    """A late failure must restore app, runtime, launcher, repair exe, and support."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)

    with pytest.raises(RuntimeError, match="rolled back"):
        RepairExecutionService(
            runtime_provisioner=_RuntimeProvisioner(),
            state_writer=_RejectingStateWriter(),
        ).execute_application(request)

    assert (layout.app_dir / "substitute" / "_version.py").read_text(
        encoding="utf-8"
    ) == '__version__ = "0.9.0"\n'
    assert layout.runtime_python.read_bytes() == b"old-python"
    assert layout.executable_path.read_bytes() == b"old-launcher"
    assert (
        layout.launcher_support_path / "LauncherUi.exe"
    ).read_bytes() == b"old-launcher-ui"
    assert (layout.launcher_support_path / "Repair.exe").read_bytes() == b"old-repair"
    assert (layout.launcher_support_path / "runtime.dll").read_bytes() == b"old-support"


def test_execution_repairs_only_owned_nodes_when_managed_ownership_is_proven(
    tmp_path: Path,
) -> None:
    """Standard repair may reach into managed Comfy only for the two owned folders."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    settings = layout.user_dir / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "comfy_target.json").write_text(
        "{\n"
        '  "mode": "managed_local",\n'
        f'  "workspace_path": "{str(layout.root / "comfyui").replace(chr(92), chr(92) * 2)}",\n'
        '  "install_owned": true\n'
        "}\n",
        encoding="utf-8",
    )
    custom_nodes = layout.root / "comfyui" / "custom_nodes"
    for name in ("substitute-backend", "SugarCubes"):
        path = custom_nodes / name
        path.mkdir()
        (path / "version.txt").write_text("old-owned", encoding="utf-8")
    third_party = custom_nodes / "third-party" / "node.py"
    before = third_party.read_bytes()

    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        comfy_repairer=_ManagedComfyRepairer(),
    ).execute_application(_prepared_request(layout))

    assert result.repaired_managed_comfy_nodes
    assert third_party.read_bytes() == before
    for name in ("substitute-backend", "SugarCubes"):
        assert (custom_nodes / name / "version.txt").read_text(
            encoding="utf-8"
        ) == "new-owned"


def test_full_managed_comfy_repair_replaces_core_and_preserves_user_roots(
    tmp_path: Path,
) -> None:
    """Full repair should promote fresh core while protected and third-party bytes survive."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    settings = layout.user_dir / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "comfy_target.json").write_text(
        "{\n"
        '  "mode": "managed_local",\n'
        f'  "workspace_path": "{str(layout.root / "comfyui").replace(chr(92), chr(92) * 2)}",\n'
        '  "install_owned": true\n'
        "}\n",
        encoding="utf-8",
    )
    workspace = layout.root / "comfyui"
    (workspace / "main.py").write_text("old-core", encoding="utf-8")
    (workspace / ".venv" / "Scripts").mkdir(parents=True)
    (workspace / ".venv" / "Scripts" / "python.exe").write_bytes(b"old")
    protected = (
        workspace / "models" / "model.safetensors",
        workspace / "user" / "workflow.json",
        workspace / "input" / "source.png",
        workspace / "output" / "result.png",
        workspace / "custom_nodes" / "third-party" / "node.py",
    )
    for index, path in enumerate(protected):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"sentinel-{index}".encode())
    before = {path: path.read_bytes() for path in protected}

    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        comfy_repairer=_ManagedComfyRepairer(),
    ).execute_application(
        _prepared_request(layout, scope=RepairScope.FULL_MANAGED_COMFY)
    )

    assert result.comfy_quarantine_root is not None
    assert (workspace / "main.py").read_text(encoding="utf-8") == "fresh-core"
    assert {path: path.read_bytes() for path in protected} == before
