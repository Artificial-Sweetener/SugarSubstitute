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

"""Exercise production reconciliation across one real in-place ComfyUI update."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import subprocess

from substitute.infrastructure.comfy.attached_install import (
    prepare_attached_comfy_setup,
)
from substitute.infrastructure.comfy.comfy_checkout_contract import (
    ComfyCheckoutContract,
)
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.manager_runtime_probe import (
    detect_workspace_manager_runtime,
)
from substitute.infrastructure.comfy.workspace_dependency_reconciler import (
    AttachedComfyRequirementsError,
    validate_attached_workspace_dependencies,
)
from tools.ci.comfy_support_matrix import matrix_entry
from tools.ci.comfy_probe_support import (
    assert_manager_requirement,
    assert_runtime,
    git_output,
    log,
    prepare_checkout,
    prepare_environment,
    probe_server,
    run_checked,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one exact upstream update through attached and managed ownership."""

    arguments = _parse_arguments(argv)
    source = matrix_entry(arguments.source_tag)
    target = matrix_entry(arguments.target_tag)
    repository_root = Path.cwd().resolve()
    workspace = (
        arguments.workspace.resolve()
        if arguments.workspace is not None
        else repository_root
        / "build"
        / "comfy-updates"
        / f"{source.comfyui_tag}-to-{target.comfyui_tag}"
    )
    prepare_checkout(workspace, source.comfyui_tag)
    python_executable = prepare_environment(repository_root, workspace)
    ensure_managed_comfy_setup(
        workspace=workspace,
        installer_temp_root=workspace.parent / "installer-temp" / "source",
        on_log=log,
    )
    source_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    assert_runtime(
        source_runtime.version,
        source_runtime.supports_pygit2,
        source.manager_version,
        source.supports_pygit2,
    )
    source_requirements = _save_contract_file(
        workspace,
        workspace.parent / f"{workspace.name}.source-requirements.txt",
        "requirements.txt",
    )
    source_manager_requirements = _save_contract_file(
        workspace,
        workspace.parent / f"{workspace.name}.source-manager-requirements.txt",
        "manager_requirements.txt",
    )

    _checkout_target(workspace, target.comfyui_tag)
    assert_manager_requirement(workspace, target.manager_version)
    target_head = git_output(workspace, "rev-parse", "HEAD")
    tracked_marker = workspace / "README.md"
    tracked_original = tracked_marker.read_text(encoding="utf-8")
    tracked_marker.write_text(
        tracked_original + "\nSugarSubstitute update preservation marker.\n",
        encoding="utf-8",
    )
    untracked_marker = workspace / "user-update-preservation-marker.txt"
    untracked_marker.write_text("preserve attached content", encoding="utf-8")
    baseline_status = git_output(
        workspace,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    baseline_diff = git_output(workspace, "diff", "--binary")

    attached_drift_detected = _repair_user_owned_comfy_dependencies(
        workspace=workspace,
        python_executable=python_executable,
    )
    prepare_attached_comfy_setup(
        workspace=workspace,
        python_executable=python_executable,
        on_log=log,
    )
    attached_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    assert_runtime(
        attached_runtime.version,
        attached_runtime.supports_pygit2,
        target.manager_version,
        target.supports_pygit2,
    )
    attached_server = probe_server(
        workspace=workspace,
        python_executable=python_executable,
        runtime=attached_runtime,
    )
    _assert_repository_preserved(
        workspace=workspace,
        expected_head=target_head,
        expected_status=baseline_status,
        expected_diff=baseline_diff,
        tracked_marker=tracked_marker,
        tracked_original=tracked_original,
        untracked_marker=untracked_marker,
    )

    _install_requirements(
        workspace=workspace,
        python_executable=python_executable,
        requirements_path=source_requirements,
    )
    _install_requirements(
        workspace=workspace,
        python_executable=python_executable,
        requirements_path=source_manager_requirements,
    )
    stale_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    manager_transition = source.manager_version != target.manager_version
    if manager_transition and stale_runtime.version != source.manager_version:
        raise RuntimeError(
            "Could not recreate the source Manager before managed reconciliation."
        )

    ensure_managed_comfy_setup(
        workspace=workspace,
        installer_temp_root=workspace.parent / "installer-temp" / "target",
        on_log=log,
    )
    managed_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    assert_runtime(
        managed_runtime.version,
        managed_runtime.supports_pygit2,
        target.manager_version,
        target.supports_pygit2,
    )
    managed_server = probe_server(
        workspace=workspace,
        python_executable=python_executable,
        runtime=managed_runtime,
    )
    _assert_success_state(workspace, target.comfyui_tag)
    _assert_repository_preserved(
        workspace=workspace,
        expected_head=target_head,
        expected_status=baseline_status,
        expected_diff=baseline_diff,
        tracked_marker=tracked_marker,
        tracked_original=tracked_original,
        untracked_marker=untracked_marker,
    )
    print(
        json.dumps(
            {
                "source_tag": source.comfyui_tag,
                "source_manager": source.manager_version,
                "target_tag": target.comfyui_tag,
                "target_manager": managed_runtime.version,
                "manager_transition_recreated": manager_transition,
                "attached_dependency_drift_detected": attached_drift_detected,
                "attached_flow": "passed",
                "managed_flow": "passed",
                "attached_repository_preserved": True,
                "success_state_committed": True,
                "attached_server": attached_server,
                "managed_server": managed_server,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse one reviewed source and target tag pair."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--source-tag", required=True)
    parser.add_argument("--target-tag", required=True)
    parser.add_argument("--workspace", type=Path)
    return parser.parse_args(argv)


def _checkout_target(workspace: Path, tag: str) -> None:
    """Simulate an external updater changing only the ComfyUI checkout."""

    run_checked(
        [
            "git",
            "fetch",
            "--depth",
            "1",
            "origin",
            f"refs/tags/{tag}:refs/tags/{tag}",
        ],
        cwd=workspace,
    )
    run_checked(["git", "checkout", "--detach", tag], cwd=workspace)


def _save_contract_file(workspace: Path, destination: Path, name: str) -> Path:
    """Preserve one source dependency contract outside the checkout."""

    destination.write_bytes((workspace / name).read_bytes())
    return destination


def _repair_user_owned_comfy_dependencies(
    *,
    workspace: Path,
    python_executable: Path,
) -> bool:
    """Simulate the attached owner repairing detected dependency drift."""

    try:
        validate_attached_workspace_dependencies(
            workspace=workspace,
            python_executable=python_executable,
        )
    except AttachedComfyRequirementsError:
        _install_requirements(
            workspace=workspace,
            python_executable=python_executable,
            requirements_path=workspace / "requirements.txt",
        )
        return True
    return False


def _install_requirements(
    *,
    workspace: Path,
    python_executable: Path,
    requirements_path: Path,
) -> None:
    """Apply a simulated user-owned requirements transaction headlessly."""

    subprocess.run(
        [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "--requirement",
            str(requirements_path),
        ],
        cwd=workspace,
        check=True,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )


def _assert_repository_preserved(
    *,
    workspace: Path,
    expected_head: str,
    expected_status: str,
    expected_diff: str,
    tracked_marker: Path,
    tracked_original: str,
    untracked_marker: Path,
) -> None:
    """Verify production flows preserve tracked and untracked attached content."""

    if git_output(workspace, "rev-parse", "HEAD") != expected_head:
        raise RuntimeError("Reconciliation changed the attached checkout revision.")
    if (
        git_output(
            workspace,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        != expected_status
    ):
        raise RuntimeError("Reconciliation changed attached repository status.")
    if git_output(workspace, "diff", "--binary") != expected_diff:
        raise RuntimeError("Reconciliation changed attached tracked content.")
    if tracked_marker.read_text(encoding="utf-8") != (
        tracked_original + "\nSugarSubstitute update preservation marker.\n"
    ):
        raise RuntimeError("Reconciliation changed the tracked user marker.")
    if untracked_marker.read_text(encoding="utf-8") != "preserve attached content":
        raise RuntimeError("Reconciliation changed the untracked user marker.")


def _assert_success_state(workspace: Path, target_tag: str) -> None:
    """Verify managed reconciliation atomically recorded validated target state."""

    path = workspace / ".substitute" / "managed_setup_freshness.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise RuntimeError("Managed reconciliation did not record successful state.")
    expected_version = target_tag.removeprefix("v")
    snapshot = ComfyCheckoutContract(workspace).capture()
    if snapshot.version != expected_version:
        raise RuntimeError("Managed reconciliation state targets the wrong checkout.")
    key = payload.get("key")
    checkout_contract = key.get("checkout_contract") if isinstance(key, dict) else None
    if not isinstance(checkout_contract, dict):
        raise RuntimeError("Managed reconciliation state has no checkout evidence.")
    requirements = checkout_contract.get("requirements")
    manager_requirements = checkout_contract.get("manager_requirements")
    if not isinstance(requirements, dict) or (
        requirements.get("sha256") != snapshot.comfy_requirements_digest
    ):
        raise RuntimeError("Managed state does not match target Comfy requirements.")
    if not isinstance(manager_requirements, dict) or (
        manager_requirements.get("sha256") != snapshot.manager_requirements_digest
    ):
        raise RuntimeError("Managed state does not match target Manager requirements.")


if __name__ == "__main__":
    raise SystemExit(main())
