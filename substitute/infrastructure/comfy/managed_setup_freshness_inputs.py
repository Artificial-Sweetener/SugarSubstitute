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

"""Build semantic and filesystem inputs for managed-setup freshness."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.managed_acceleration_policy import (
    managed_acceleration_policy_fingerprint,
)
from substitute.infrastructure.comfy.managed_runtime_configuration_codec import (
    enum_value,
)
from substitute.infrastructure.comfy.managed_setup_evidence import (
    content_signature,
    path_signature,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
    workspace_venv_dir,
)
from substitute.infrastructure.comfy.manager_environment import (
    integrated_manager_pygit2_requirement,
)
from substitute.infrastructure.comfy.nodepack_manifest import (
    CORE_COMFY_NODEPACKS,
    SUGARCUBES_BASE_NODEPACK_INSTALLS,
    SUGARCUBES_COMPANION_NODEPACKS,
    CoreComfyNodepack,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    resolve_installed_nodepack_root,
)
from substitute.infrastructure.comfy.sugarcubes_installation_contract import (
    sugarcubes_maintenance_path,
    sugarcubes_root,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    repository_service,
)


def installed_setup_freshness_key(
    *,
    workspace: Path,
    strategy: object,
) -> dict[str, object]:
    """Build a stable key for recurring installed-workspace setup checks."""

    key = installed_setup_static_freshness_key(workspace)
    key["strategy"] = _strategy_freshness_key(strategy)
    return key


def installed_setup_static_freshness_key(workspace: Path) -> dict[str, object]:
    """Build setup inputs whose evaluation does not probe accelerator hardware."""

    return {
        "schema_version": 5,
        "checkout_contract": {
            "version": content_signature(workspace / "comfyui_version.py"),
            "requirements": content_signature(workspace / "requirements.txt"),
            "manager_requirements": content_signature(
                workspace / "manager_requirements.txt"
            ),
        },
        "workspace": {
            "python": path_signature(workspace_python_path(workspace)),
            "main": path_signature(workspace_main_path(workspace)),
            "site_packages": _site_packages_signature(workspace),
        },
        "manager": _manager_freshness_key(workspace),
        "core_nodepacks": [
            _core_nodepack_freshness_key(workspace, nodepack)
            for nodepack in CORE_COMFY_NODEPACKS
        ],
        "sugarcubes_baseline": _sugarcubes_baseline_freshness_key(workspace),
        "managed_acceleration": {
            "policy_fingerprint": managed_acceleration_policy_fingerprint(),
        },
    }


def installed_setup_freshness_request(
    *,
    force_cpu_mode: bool,
    prefer_edge_torch: bool,
    prefer_edge_comfy_channel: bool,
) -> dict[str, object]:
    """Return caller preferences that can change runtime selection."""

    return {
        "force_cpu_mode": force_cpu_mode,
        "prefer_edge_torch": prefer_edge_torch,
        "prefer_edge_comfy_channel": prefer_edge_comfy_channel,
    }


def _strategy_freshness_key(strategy: object) -> dict[str, object]:
    """Return install strategy fields that affect setup validity."""

    python_runtime = getattr(strategy, "python_runtime", None)
    torch_policy = getattr(strategy, "torch_policy", None)
    return {
        "target": enum_value(getattr(strategy, "target", None)),
        "python_version": getattr(python_runtime, "selected_version", None),
        "python_executable": str(getattr(python_runtime, "executable", "")),
        "python_fallback_used": bool(getattr(python_runtime, "used_fallback", False)),
        "comfy_channel": enum_value(getattr(strategy, "comfy_channel", None)),
        "stability": enum_value(getattr(strategy, "stability", None)),
        "torch_backend_key": getattr(torch_policy, "backend_key", None),
        "torch_release_channel": enum_value(
            getattr(torch_policy, "release_channel", None)
        ),
        "torch_selection_reason": getattr(torch_policy, "selection_reason", None),
        "torch_install_arguments": list(
            getattr(torch_policy, "install_arguments", ()) or ()
        ),
        "torch_fallback_backend_key": getattr(
            torch_policy, "fallback_backend_key", None
        ),
        "torch_fallback_release_channel": enum_value(
            getattr(torch_policy, "fallback_release_channel", None)
        ),
        "torch_fallback_install_arguments": list(
            getattr(torch_policy, "fallback_install_arguments", ()) or ()
        ),
        "validation_expected": enum_value(
            getattr(torch_policy, "validation_expected", None)
        ),
    }


def _manager_freshness_key(workspace: Path) -> dict[str, object]:
    """Return integrated Manager contract files that affect setup validity."""

    return {
        "kind": "integrated",
        "optional_pygit2_backend": integrated_manager_pygit2_requirement(),
        "requirements": content_signature(workspace / "manager_requirements.txt"),
        "launch_contract": content_signature(workspace / "comfy" / "cli_args.py"),
    }


def _core_nodepack_freshness_key(
    workspace: Path,
    nodepack: CoreComfyNodepack,
) -> dict[str, object]:
    """Return freshness inputs for one required core nodepack."""

    nodepack_root = resolve_installed_nodepack_root(workspace, nodepack)
    return {
        "id": nodepack.nodepack_id.value,
        "registry": nodepack.registry_id,
        "required_version": nodepack.required_version,
        "folder": str(nodepack_root.relative_to(workspace)),
        "folder_signature": path_signature(nodepack_root),
        "git": _git_head_signature(nodepack_root),
        "project_manifest": content_signature(nodepack_root / "pyproject.toml"),
        "registry_tracking": content_signature(nodepack_root / ".tracking"),
        "sentinels": [
            path_signature(nodepack_root / sentinel)
            for sentinel in nodepack.sentinel_files
        ],
        "fallback_repository": nodepack.fallback_repository_url,
        "fallback_archive": nodepack.fallback_archive_url,
    }


def _sugarcubes_baseline_freshness_key(workspace: Path) -> dict[str, object]:
    """Return inputs for SugarCubes baseline dependency maintenance."""

    installed_sugarcubes_root = sugarcubes_root(workspace)
    return {
        "maintenance": path_signature(sugarcubes_maintenance_path(workspace)),
        "host_api": path_signature(
            installed_sugarcubes_root / "sugarcubes" / "host_api.py"
        ),
        "install_mapping": {
            node_id: [
                {
                    "source_url": candidate.source_url,
                    "target_folder_name": candidate.target_folder_name,
                }
                for candidate in candidates
            ]
            for node_id, candidates in sorted(SUGARCUBES_BASE_NODEPACK_INSTALLS.items())
        },
        "companions": {
            node_id: list(companions)
            for node_id, companions in sorted(SUGARCUBES_COMPANION_NODEPACKS.items())
        },
    }


def _site_packages_signature(workspace: Path) -> dict[str, object]:
    """Return a coarse signature for the managed site-packages root."""

    venv_dir = workspace_venv_dir(workspace)
    candidates = [venv_dir / "Lib" / "site-packages"]
    lib_dir = venv_dir / "lib"
    if lib_dir.exists():
        candidates.extend(lib_dir.glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.exists():
            return path_signature(candidate)
    return {"exists": False}


def _git_head_signature(path: Path) -> dict[str, object]:
    """Return a lightweight git HEAD signature for a checkout path."""

    if not (path / ".git").exists():
        return {"exists": False}
    try:
        head_commit = repository_service().head_commit_id(path)
    except RepositoryOperationError:
        return {"exists": False}
    return {"exists": True, "head": head_commit}


__all__ = [
    "installed_setup_freshness_key",
    "installed_setup_freshness_request",
    "installed_setup_static_freshness_key",
]
