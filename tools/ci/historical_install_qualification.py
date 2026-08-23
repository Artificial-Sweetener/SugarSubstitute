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

"""Prepare real historical installations and verify state survives updates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.comfy.backend_model_root_configurator import (
    configure_backend_model_root,
)
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.hardware_models import (
    AcceleratorClass,
    ManagedPlatform,
)
from substitute.infrastructure.comfy.install_targets import ManagedInstallTarget
from substitute.infrastructure.comfy.managed_environment_validator import (
    validate_managed_environment,
)
from substitute.infrastructure.comfy.managed_setup_cache_storage import (
    prepare_managed_setup_cache,
)
from substitute.infrastructure.comfy.managed_setup_freshness_cache import (
    write_installed_setup_freshness,
)
from substitute.infrastructure.comfy.managed_setup_freshness_inputs import (
    installed_setup_freshness_request,
    installed_setup_static_freshness_key,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_managed_workspace_manager,
)
from substitute.infrastructure.comfy.sugarcubes_maintenance_runner import (
    run_sugarcubes_baseline_maintenance,
)
from substitute.infrastructure.onboarding.file_comfy_target_repository import (
    FileComfyTargetConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_installation_repository import (
    FileInstallationConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_managed_runtime_repository import (
    FileManagedRuntimeConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_runtime_repository import (
    FileRuntimeConfigurationRepository,
)
from tools.ci.comfy_probe_support import prepare_checkout, prepare_environment
from tools.ci.comfy_support_matrix import COMFY_SUPPORT_MATRIX
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def prepare_portable_historical_install(
    *,
    repository_root: Path,
    installer_path: Path,
    install_root: Path,
    manifest_url: str,
    historical_version: str,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    timeout_seconds: float,
    environment: dict[str, str] | None = None,
) -> None:
    """Complete the native historical installer contract without launching it."""

    command = [
        str(installer_path.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
        f"--manifest-url={manifest_url}",
    ]
    result = subprocess.run(
        command,
        cwd=installer_path.resolve().parent,
        env=dict(os.environ if environment is None else environment),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Historical installer exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    materialize_historical_managed_configuration(
        repository_root=repository_root,
        install_root=install_root,
        endpoint_port=endpoint_port,
        managed_workspace=managed_workspace,
        managed_model_root=managed_model_root,
    )
    print(
        f"HISTORICAL_INSTALLER_COMPLETED version={historical_version}",
        flush=True,
    )


def install_candidate_over_historical_install(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str | None,
    timeout_seconds: float,
    environment: dict[str, str],
) -> None:
    """Install candidate bytes over one completed historical installation."""

    command = [
        str(installer_path.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
    ]
    if manifest_url is not None:
        command.append(f"--manifest-url={manifest_url}")
    result = subprocess.run(
        command,
        cwd=installer_path.resolve().parent,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise InstallerLifecycleError(
            f"Candidate installer update exited with {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def materialize_historical_managed_configuration(
    *,
    repository_root: Path,
    install_root: Path,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
) -> None:
    """Prepare a real managed target representing an established user install."""

    installation = InstallationConfiguration.create_default(install_root)
    for required_path in (
        installation.user_settings_dir,
        installation.projects_dir,
        installation.outputs_dir,
        installation.wildcards_dir,
        installation.runtime_state_dir,
        managed_model_root,
    ):
        required_path.mkdir(parents=True, exist_ok=True)
    FileInstallationConfigurationRepository(install_root).save(installation)
    layout = InstallLayout.from_root(install_root)
    FileRuntimeConfigurationRepository(installation).save(
        RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=layout.runtime_python,
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
    )
    FileComfyTargetConfigurationRepository(installation).save(
        ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=endpoint_port),
            workspace_path=managed_workspace,
            install_owned=True,
            launch_owned=True,
        )
    )
    qualification_release = COMFY_SUPPORT_MATRIX[-1]
    prepare_checkout(managed_workspace, qualification_release.comfyui_tag)
    prepare_environment(repository_root, managed_workspace)
    _prepare_qualified_existing_managed_workspace(
        workspace=managed_workspace,
        model_root=managed_model_root,
        runtime_state_dir=installation.runtime_state_dir,
    )


def _prepare_qualified_existing_managed_workspace(
    *,
    workspace: Path,
    model_root: Path,
    runtime_state_dir: Path,
) -> None:
    """Converge and record a real existing runtime without new-install selection."""

    python_executable = workspace_python_path(workspace)
    environment = dict(os.environ)
    ensure_managed_workspace_manager(
        workspace,
        python_executable=python_executable,
        env=environment,
    )
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=python_executable,
        env=environment,
    )
    run_sugarcubes_baseline_maintenance(
        workspace,
        python_executable=python_executable,
        env=environment,
    )
    configure_backend_model_root(
        workspace=workspace,
        python_executable=python_executable,
        model_root=model_root,
    )
    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=AcceleratorClass.CPU,
    )
    if not validation.success:
        raise InstallerLifecycleError(validation.detail)

    platform, target = _existing_qualification_target()
    force_cpu_mode = sys.platform != "darwin"
    runtime_configuration = ManagedRuntimeConfiguration(
        workspace_path=str(workspace.resolve()),
        detected_platform=platform.value,
        detected_accelerator=validation.detected_backend,
        install_target=target.value,
        backend_policy=validation.detected_backend,
        torch_release_channel=validation.detected_torch_channel,
        torch_selection_reason="Validated existing qualification runtime.",
        force_cpu_mode=force_cpu_mode,
        validation_status=ManagedRuntimeValidationStatus.VALID,
        validation_detail=validation.detail,
    )
    FileManagedRuntimeConfigurationRepository(runtime_state_dir).save(
        runtime_configuration
    )
    freshness_key = installed_setup_static_freshness_key(workspace)
    freshness_key["strategy"] = {
        "source": "existing_qualification_runtime",
        "target": target.value,
    }
    cache = prepare_managed_setup_cache(workspace)
    try:
        write_installed_setup_freshness(
            record_path=cache.record_path,
            key=freshness_key,
            request=installed_setup_freshness_request(
                force_cpu_mode=force_cpu_mode,
                prefer_edge_torch=False,
                prefer_edge_comfy_channel=False,
            ),
            runtime_configuration=runtime_configuration,
            validation=validation,
        )
    finally:
        cache.close()


def _existing_qualification_target() -> tuple[ManagedPlatform, ManagedInstallTarget]:
    """Return the existing-runtime identity for the native qualification host."""

    if sys.platform == "win32":
        return ManagedPlatform.WINDOWS, ManagedInstallTarget.WINDOWS_CPU
    if sys.platform == "darwin":
        return ManagedPlatform.MACOS, ManagedInstallTarget.MACOS_APPLE_SILICON
    return ManagedPlatform.LINUX, ManagedInstallTarget.LINUX_CPU


def seed_historical_user_configuration(
    *,
    install_root: Path,
    historical_version: str,
    managed_workspace: Path,
    managed_model_root: Path,
) -> Path:
    """Add authoritative user state whose exact survival is required after update."""

    marker = install_root / "user" / "settings" / "qualification-preservation.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "historical_version": historical_version,
                "managed_workspace": str(managed_workspace.resolve()),
                "managed_model_root": str(managed_model_root.resolve()),
                "user_value": "preserve-exactly",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return marker


def assert_historical_user_configuration_preserved(
    *,
    preservation_marker: Path,
    historical_version: str,
    managed_workspace: Path,
    managed_model_root: Path,
) -> None:
    """Require update activation to retain user state and selected target paths."""

    expected = {
        "historical_version": historical_version,
        "managed_workspace": str(managed_workspace.resolve()),
        "managed_model_root": str(managed_model_root.resolve()),
        "user_value": "preserve-exactly",
    }
    if _read_json(preservation_marker) != expected:
        raise InstallerLifecycleError(
            "Candidate update changed authoritative historical user configuration."
        )
    target = _read_json(preservation_marker.parent / "comfy_target.json")
    if target.get("mode") != "managed_local":
        raise InstallerLifecycleError(
            "Candidate update changed the historical target mode."
        )
    if target.get("workspace_path") != str(managed_workspace.resolve()):
        raise InstallerLifecycleError(
            "Candidate update changed the historical managed workspace."
        )


def _read_json(path: Path) -> dict[str, object]:
    """Load one required authoritative-state JSON object."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            f"Historical user configuration is invalid: {path}."
        ) from error
    if not isinstance(payload, dict):
        raise InstallerLifecycleError(
            f"Historical user configuration is not an object: {path}."
        )
    return payload


__all__ = [
    "assert_historical_user_configuration_preserved",
    "install_candidate_over_historical_install",
    "materialize_historical_managed_configuration",
    "prepare_portable_historical_install",
    "seed_historical_user_configuration",
]
