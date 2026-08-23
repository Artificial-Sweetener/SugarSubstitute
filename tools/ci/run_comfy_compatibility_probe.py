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

"""Exercise installer and launch contracts against one real upstream tag."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path

from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_attached_workspace_manager,
    ensure_managed_workspace_manager,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    detect_workspace_manager_runtime,
)
from tools.ci.comfy_probe_support import (
    assert_manager_requirement,
    assert_runtime,
    git_output,
    log,
    prepare_checkout,
    prepare_environment,
    probe_server,
)
from tools.ci.comfy_support_matrix import matrix_entry


def main(argv: Sequence[str] | None = None) -> int:
    """Run one exact-tag compatibility probe and report structured evidence."""

    arguments = _parse_arguments(argv)
    entry = matrix_entry(arguments.comfyui_tag)
    repository_root = Path.cwd().resolve()
    workspace = (
        arguments.workspace.resolve()
        if arguments.workspace is not None
        else repository_root / "build" / "comfy-compatibility" / entry.comfyui_tag
    )
    prepare_checkout(workspace, entry.comfyui_tag)
    python_executable = prepare_environment(repository_root, workspace)
    original_head = git_output(workspace, "rev-parse", "HEAD")
    assert_manager_requirement(workspace, entry.manager_version)

    managed_runtime = ensure_managed_workspace_manager(
        workspace,
        python_executable=python_executable,
        on_log=log,
    )
    assert_runtime(
        managed_runtime.version,
        managed_runtime.supports_pygit2,
        entry.manager_version,
        entry.supports_pygit2,
    )
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=python_executable,
        on_log=log,
    )

    preservation_marker = workspace / "custom_nodes" / "User-Owned-Node" / "data.txt"
    preservation_marker.parent.mkdir(parents=True, exist_ok=True)
    preservation_marker.write_text("preserve attached content", encoding="utf-8")
    attached_runtime = ensure_attached_workspace_manager(
        workspace,
        python_executable=python_executable,
        on_log=log,
    )
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=python_executable,
        on_log=log,
    )
    if preservation_marker.read_text(encoding="utf-8") != "preserve attached content":
        raise RuntimeError(
            "Attached provisioning modified user-owned custom-node data."
        )
    if git_output(workspace, "rev-parse", "HEAD") != original_head:
        raise RuntimeError(
            "Attached provisioning changed the ComfyUI checkout revision."
        )
    if git_output(workspace, "diff", "--name-only"):
        raise RuntimeError("Installer modified tracked files in the attached checkout.")
    if attached_runtime.kind is not managed_runtime.kind:
        raise RuntimeError(
            "Managed and attached probes selected different Manager kinds."
        )

    launch_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=python_executable,
    )
    evidence = probe_server(
        workspace=workspace,
        python_executable=python_executable,
        runtime=launch_runtime,
    )
    print(
        json.dumps(
            {
                "comfyui_tag": entry.comfyui_tag,
                "manager_version": launch_runtime.version,
                "manager_supports_pygit2": launch_runtime.supports_pygit2,
                "manager_uses_pygit2": launch_runtime.uses_pygit2,
                "managed_flow": "passed",
                "attached_flow": "passed",
                "tracked_checkout_preserved": True,
                **evidence,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the exact upstream tag and optional prepared workspace."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui-tag", required=True)
    parser.add_argument("--workspace", type=Path)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
