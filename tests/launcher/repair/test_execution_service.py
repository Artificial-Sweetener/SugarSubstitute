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
from collections.abc import Mapping, Sequence
import sys

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import (
    RepairScope,
)
from launcher.sugarsubstitute_launcher.application.repair.execution_service import (
    RepairExecutionService,
)
from launcher.sugarsubstitute_launcher.application.repair.integrity import (
    directory_tree_sha256,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from sugarsubstitute_shared.launcher_update.bundle_selection import (
    LauncherBundleSelection,
)
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair
from launcher.sugarsubstitute_launcher.application.repair.progress import (
    RepairProgress,
    RepairStage,
)


from .execution_support import (
    _RuntimeProvisioner,
    _RejectingStateWriter,
    _ManagedComfyRepairer,
    _write_launcher,
    _prepared_request,
    _write_old_install,
)


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
    assert layout.executable_path.read_bytes() == b"old-launcher"
    assert (layout.launcher_support_path / "Repair.exe").read_bytes() == b"old-repair"
    selection = LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE)
    selected = selection.resolve()
    assert selected.version == request.version
    assert selected.root != layout.root
    assert (selected.root / "SugarSubstitute.exe").read_bytes() == b"new-launcher"
    assert (
        selected.root / "launcher-bin/LauncherUi.exe"
    ).read_bytes() == b"new-launcher-ui"
    assert (selected.root / "launcher-bin/Repair.exe").read_bytes() == b"new-repair"
    baseline_record = LauncherInstallationRecord.load(layout.launcher_installation_path)
    assert baseline_record is not None and baseline_record.version == "0.9.0"
    active_record = selection.installed_record()
    assert active_record is not None and active_record.version == request.version
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

    selection = LauncherBundleSelection(layout.root, WINDOWS_X64_BUNDLE)
    prior_staging = layout.launcher_dir / "updates" / "prior"
    _write_launcher(prior_staging)
    previous = selection.publish(prior_staging, version="0.9.1")
    selection.activate(previous)
    layout.state_path.write_bytes(b"old application state")

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
    assert selection.resolve() == previous
    assert layout.state_path.read_bytes() == b"old application state"


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


@pytest.mark.parametrize("failure_phase", [None, "provision", "validate"])
@pytest.mark.parametrize("existing_runtime", [False, True])
def test_full_managed_comfy_repair_replaces_core_and_preserves_user_roots(
    tmp_path: Path,
    failure_phase: str | None,
    existing_runtime: bool,
) -> None:
    """Construct at the final path, preserve user data, and roll back either runtime failure."""

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
    if existing_runtime:
        (workspace / ".venv" / "Scripts").mkdir(parents=True)
        (workspace / ".venv" / "Scripts" / "python.exe").write_bytes(b"old")
    protected = (
        workspace / "models" / "model.safetensors",
        workspace / "user" / "workflow.json",
        workspace / "input" / "source.png",
        workspace / "output" / "result.png",
        workspace / "custom_nodes" / "third-party" / "node.py",
        workspace / "custom_nodes" / "SugarCubes" / ".sugarcubes" / "authored.cube",
        workspace / ".substitute" / "model_root.json",
    )
    for index, path in enumerate(protected):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"sentinel-{index}".encode())
    before = {path: path.read_bytes() for path in protected}

    events: list[RepairProgress] = []
    service = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        comfy_repairer=_ManagedComfyRepairer(failure_phase),
        progress_observer=events.append,
    )
    request = _prepared_request(layout, scope=RepairScope.FULL_MANAGED_COMFY)
    if failure_phase is not None:
        with pytest.raises(RuntimeError, match="rolled back"):
            service.execute_application(request)
        assert (workspace / "main.py").read_text(encoding="utf-8") == "old-core"
        if existing_runtime:
            assert (
                workspace / ".venv" / "Scripts" / "python.exe"
            ).read_bytes() == b"old"
        else:
            assert not (workspace / ".venv").exists()
        assert {path: path.read_bytes() for path in protected} == before
        assert events[-1].stage is not None
        assert not (layout.root / ".repair" / "pending.json").exists()
        return
    result = service.execute_application(request)

    assert result.comfy_quarantine_root is not None
    assert (workspace / "main.py").read_text(encoding="utf-8") == "fresh-core"
    assert {path: path.read_bytes() for path in protected} == before
    assert [event.stage for event in events] == [
        RepairStage.VALIDATE_INPUT,
        RepairStage.RESTORE_APPLICATION,
        RepairStage.PREPARE_RUNTIME,
        RepairStage.SAVE_STATE,
        RepairStage.VALIDATE_APPLICATION,
        RepairStage.PREPARE_COMFY,
        RepairStage.RESTORE_COMFY,
        RepairStage.VALIDATE_COMFY,
        None,
    ]
    assert [event.completed for event in events] == list(range(9))
    assert {event.total for event in events} == {8}


@pytest.mark.parametrize("reject", [False, True])
def test_progress_reaches_completion_only_after_successful_commit(
    tmp_path: Path,
    reject: bool,
) -> None:
    """A rolled-back repair must never emit successful terminal progress."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    events: list[RepairProgress] = []
    service = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        state_writer=_RejectingStateWriter() if reject else None,
        progress_observer=events.append,
    )
    request = _prepared_request(layout)
    if reject:
        with pytest.raises(RuntimeError, match="rolled back"):
            service.execute_application(request)
    else:
        service.execute_application(request)
    assert [event.stage for event in events[:5]] == [
        RepairStage.VALIDATE_INPUT,
        RepairStage.RESTORE_APPLICATION,
        RepairStage.PREPARE_RUNTIME,
        RepairStage.SAVE_STATE,
        RepairStage.VALIDATE_APPLICATION,
    ]
    assert [event.completed for event in events] == list(range(5 if reject else 6))
    assert {event.total for event in events} == {5}
    assert (events[-1].stage is None) is not reject


def test_progress_observer_failure_cannot_abort_repair(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep presentation callbacks outside the repair transaction's failure contract."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)

    def broken_observer(progress: RepairProgress) -> None:
        """Reject a real stage report at the presentation boundary."""
        raise RuntimeError(f"presentation failed at {progress.stage}")

    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        progress_observer=broken_observer,
    ).execute_application(_prepared_request(layout))
    assert result.version == "1.2.3"
    assert "Repair progress observer failed" in caplog.text


def test_failed_repair_can_retry_without_downloading_or_rebuilding_its_inputs(
    tmp_path: Path,
) -> None:
    """A retry uses the same verified source after the first candidate is rolled back."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    request = _prepared_request(layout)
    rejecting = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner(),
        state_writer=_RejectingStateWriter(),
    )
    with pytest.raises(RuntimeError, match="rolled back"):
        rejecting.execute_application(request)
    assert directory_tree_sha256(request.staged_app_dir) == request.staged_app_sha256
    assert (
        directory_tree_sha256(request.staged_launcher_dir)
        == request.staged_launcher_sha256
    )
    result = RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner()
    ).execute_application(request)
    assert result.version == request.version
    assert directory_tree_sha256(request.staged_app_dir) == request.staged_app_sha256
    assert (
        directory_tree_sha256(request.staged_launcher_dir)
        == request.staged_launcher_sha256
    )


def test_detached_repair_bootstraps_runtime_from_its_bundled_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebuild a removed runtime through the real helper and bundled uv owner."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    layout.uv_executable.parent.mkdir(parents=True, exist_ok=True)
    layout.uv_executable.write_bytes(b"old-uv")
    managed_state = layout.appdata_dir / "runtime_state" / "managed_runtime.json"
    managed_state.parent.mkdir(parents=True)
    managed_state.write_bytes(
        b'{"workspace_path":"comfyui","validation_status":"valid"}'
    )
    original_managed_state = managed_state.read_bytes()
    bundle = tmp_path / "helper-bundle"
    bundled_uv = bundle / "launcher_assets" / WINDOWS_X64.uv_executable_name
    bundled_uv.parent.mkdir(parents=True)
    bundled_uv.write_bytes(b"bundled-uv")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    request = _prepared_request(layout)
    request_path = layout.root / ".repair" / "prepared.json"
    request.save(request_path)
    commands: list[tuple[str, ...]] = []

    def run_command(
        self: SubprocessRuntimeCommandRunner,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Model subprocess output while retaining real runtime orchestration."""
        del self, env
        assert cwd == layout.root
        assert layout.uv_executable.read_bytes() == b"bundled-uv"
        commands.append(tuple(command))
        if "venv" in command:
            layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
            layout.runtime_python.write_bytes(b"candidate-python")

    monkeypatch.setattr(SubprocessRuntimeCommandRunner, "run", run_command)
    result = run_prepared_repair(request_path)

    assert result.version == request.version
    assert not request_path.exists()
    assert layout.runtime_python.read_bytes() == b"candidate-python"
    assert layout.uv_executable.read_bytes() == b"bundled-uv"
    assert managed_state.read_bytes() == original_managed_state
    assert any("venv" in command for command in commands)
    assert (layout.user_dir / "projects" / "work.json").read_bytes() == b"protected-0"


def test_repair_preserves_live_crash_diagnostics_and_child_output(
    tmp_path: Path,
) -> None:
    """Repair must not move files its own live diagnostic writers still hold open."""
    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    fault = layout.appdata_dir / "diagnostics" / "python-fault.log"
    child_log = layout.root / ".repair" / "diagnostics" / "repair-child.log"
    for path in (fault, child_log):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"retained diagnostic\n")
    request = _prepared_request(layout)
    with fault.open("ab") as fault_stream, child_log.open("ab") as child_stream:
        RepairExecutionService(
            runtime_provisioner=_RuntimeProvisioner()
        ).execute_application(request)
        fault_stream.write(b"crash runtime still active\n")
        child_stream.write(b"repair worker finished\n")
    assert fault.read_bytes() == b"retained diagnostic\ncrash runtime still active\n"
    assert child_log.read_bytes() == b"retained diagnostic\nrepair worker finished\n"


@pytest.mark.parametrize("enabled", [False, True])
def test_repair_retains_update_preferences(tmp_path: Path, enabled: bool) -> None:
    """Repair must retain update consent and cadence while replacing damaged state."""
    from launcher.sugarsubstitute_launcher.config import (
        LauncherConfig,
        UpdateCheckConfig,
    )

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    _write_old_install(layout)
    preferences = UpdateCheckConfig(enabled=enabled, frequency="weekly")
    LauncherConfig.from_layout(layout=layout, update_check=preferences).save(
        layout.config_path
    )
    RepairExecutionService(
        runtime_provisioner=_RuntimeProvisioner()
    ).execute_application(_prepared_request(layout))
    assert LauncherConfig.load(layout.config_path).update_check == preferences
