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

"""Verify live managed Comfy integrity for installer qualification."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.request

from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan
from substitute.domain.comfy_nodepacks import (
    SUGARCUBES_REQUIRED_VERSION,
    SUBSTITUTE_BACKEND_REQUIRED_VERSION,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_shutdown import kill_managed_comfy_metadata
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def assert_real_managed_comfy(
    *,
    install_root: Path,
    plan: InstallerQualificationPlan,
    require_current_nodepack_versions: bool = True,
    require_governed_setup_record: bool = True,
) -> None:
    """Require the button-launched shell to own a complete live managed backend."""

    workspace = plan.managed_workspace_path
    model_root = plan.managed_model_root
    if workspace is None or model_root is None:
        raise InstallerLifecycleError(
            "Managed installer qualification omitted its workspace or model root."
        )
    if not workspace_main_path(workspace).is_file():
        raise InstallerLifecycleError("Managed Comfy installation has no main.py.")
    if not workspace_python_path(workspace).is_file():
        raise InstallerLifecycleError(
            "Managed Comfy installation has no runtime Python."
        )
    _assert_setup_evidence(
        workspace,
        require_governed_setup_record=require_governed_setup_record,
    )
    base_url = f"http://{plan.endpoint_host}:{plan.endpoint_port}"
    system = _get_json(f"{base_url}/system_stats").get("system")
    if not isinstance(system, dict) or not system.get("comfyui_version"):
        raise InstallerLifecycleError(
            "Live managed Comfy system metadata is incomplete."
        )
    object_info = _get_json(f"{base_url}/object_info")
    required_node_classes = {
        "SimpleSyrup.ResizeImageToTarget",
        "SimpleSyrup.ScaleFactor",
        "SimpleSyrup.VAEDecodeOptions",
        "SimpleSyrup.VAEEncodeOptions",
        "UpscaleModelLoader",
    }
    missing = sorted(required_node_classes.difference(object_info))
    if missing:
        raise InstallerLifecycleError(
            "Live managed Comfy is missing required node classes: " + ", ".join(missing)
        )
    capabilities = _get_json(f"{base_url}/substitute/v1/capabilities")
    if require_current_nodepack_versions and (
        capabilities.get("extensionVersion") != SUBSTITUTE_BACKEND_REQUIRED_VERSION
    ):
        raise InstallerLifecycleError(
            "Live Substitute BackEnd version does not match the packaged contract."
        )
    cube_library = capabilities.get("cubeLibrary")
    if not isinstance(cube_library, dict):
        raise InstallerLifecycleError(
            "Live SugarCubes capability metadata is incomplete."
        )
    if require_current_nodepack_versions and (
        cube_library.get("sugarCubesVersion") != SUGARCUBES_REQUIRED_VERSION
    ):
        raise InstallerLifecycleError(
            "Live SugarCubes version does not match the packaged contract."
        )
    model_status = _get_json(f"{base_url}/substitute/v1/environment/model-root")
    expected_model_root = str(model_root.resolve())
    if (
        model_status.get("configuredModelRoot") != expected_model_root
        or model_status.get("activeModelRoot") != expected_model_root
    ):
        raise InstallerLifecycleError(
            "Managed Comfy did not preserve the authoritative model-root selection."
        )
    if not (install_root / "appdata" / "runtime_state").is_dir():
        raise InstallerLifecycleError(
            "Managed process ownership state was not created."
        )


def terminate_owned_managed_comfy(install_root: Path) -> None:
    """Stop only the managed Comfy process registered by this install root."""

    metadata = ManagedProcessRegistry(install_root / "appdata" / "runtime_state").load()
    if metadata is not None:
        kill_managed_comfy_metadata(metadata)


def _assert_setup_evidence(
    workspace: Path,
    *,
    require_governed_setup_record: bool,
) -> None:
    """Require non-overlapping successful setup evidence when requested."""

    records = tuple(
        (workspace / ".substitute" / "cache" / "managed").glob(
            "managed-comfy/setup-evidence/*/record.json"
        )
    )
    if len(records) > 1:
        raise InstallerLifecycleError(
            "Managed Comfy installation retained overlapping governed setup records."
        )
    if records:
        if _read_json(records[0]).get("success") is not True:
            raise InstallerLifecycleError(
                "Managed setup evidence did not record success."
            )
    elif require_governed_setup_record:
        raise InstallerLifecycleError(
            "Managed Comfy installation did not retain governed setup evidence."
        )


def _get_json(url: str) -> dict[str, object]:
    """Load one live loopback JSON object with a bounded timeout."""

    try:
        with urllib.request.urlopen(url, timeout=30.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            f"Live managed Comfy request failed: {url}."
        ) from error
    if not isinstance(payload, dict):
        raise InstallerLifecycleError(
            f"Live managed Comfy returned non-object JSON: {url}."
        )
    return payload


def _read_json(path: Path) -> dict[str, object]:
    """Load one required managed setup record."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            f"Managed setup evidence is invalid: {path}."
        ) from error
    if not isinstance(payload, dict):
        raise InstallerLifecycleError(
            f"Managed setup evidence is not an object: {path}."
        )
    return payload


__all__ = ["assert_real_managed_comfy", "terminate_owned_managed_comfy"]
