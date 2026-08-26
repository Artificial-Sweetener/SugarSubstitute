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

"""Materialize qualified historical managed-Comfy state in an owned process."""

from __future__ import annotations

import argparse
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
from tools.ci.comfy_probe_support import prepare_environment
from tools.ci.comfy_source_checkout import prepare_checkout
from tools.ci.comfy_support_matrix import COMFY_SUPPORT_MATRIX
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.owned_process_runner import run_owned_process


def materialize_historical_managed_configuration(
    *,
    repository_root: Path,
    install_root: Path,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    source_repository: Path,
    timeout_seconds: float,
) -> None:
    """Prepare historical managed state in a bounded, fully owned child tree."""

    command = [
        sys.executable,
        "-m",
        "tools.ci.historical_managed_configuration",
        "--repository-root",
        str(repository_root.resolve()),
        "--install-root",
        str(install_root.resolve()),
        "--endpoint-port",
        str(endpoint_port),
        "--managed-workspace",
        str(managed_workspace.resolve()),
        "--managed-model-root",
        str(managed_model_root.resolve()),
        "--source-repository",
        str(source_repository.resolve()),
    ]
    try:
        result = run_owned_process(
            command,
            cwd=repository_root.resolve(),
            environment=os.environ,
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise InstallerLifecycleError(
            "Historical managed configuration did not complete within "
            f"{timeout_seconds:g} seconds.\n"
            f"stdout:\n{_timeout_output(error.stdout)}\n"
            f"stderr:\n{_timeout_output(error.stderr)}"
        ) from error
    if result.returncode != 0:
        raise InstallerLifecycleError(
            "Historical managed configuration failed with exit code "
            f"{result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)


def _materialize_historical_managed_configuration(
    *,
    repository_root: Path,
    install_root: Path,
    endpoint_port: int,
    managed_workspace: Path,
    managed_model_root: Path,
    source_repository: Path,
) -> None:
    """Create and qualify the historical managed target inside its owned child."""

    progress_path = (
        install_root / "launcher" / "logs" / "historical-materialization.log"
    )
    _record_phase(progress_path, "configuration", "started")
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
    _record_phase(progress_path, "source_checkout", "started")
    prepare_checkout(
        managed_workspace,
        qualification_release.comfyui_tag,
        source_repository=source_repository,
    )
    _record_phase(progress_path, "source_checkout", "completed")
    _record_phase(progress_path, "python_environment", "started")
    prepare_environment(repository_root, managed_workspace)
    _record_phase(progress_path, "python_environment", "completed")
    _prepare_qualified_existing_managed_workspace(
        workspace=managed_workspace,
        model_root=managed_model_root,
        runtime_state_dir=installation.runtime_state_dir,
        progress_path=progress_path,
    )
    _record_phase(progress_path, "configuration", "completed")


def _prepare_qualified_existing_managed_workspace(
    *,
    workspace: Path,
    model_root: Path,
    runtime_state_dir: Path,
    progress_path: Path,
) -> None:
    """Converge and record a real existing runtime with exact phase evidence."""

    python_executable = workspace_python_path(workspace)
    environment = dict(os.environ)
    _record_phase(progress_path, "manager", "started")
    manager_runtime = ensure_managed_workspace_manager(
        workspace,
        python_executable=python_executable,
        env=environment,
    )
    _record_phase(progress_path, "manager", "completed")
    _record_phase(progress_path, "core_nodepacks", "started")
    ensure_core_comfy_nodepacks(
        manager_runtime=manager_runtime,
        env=environment,
    )
    _record_phase(progress_path, "core_nodepacks", "completed")
    _record_phase(progress_path, "sugarcubes", "started")
    run_sugarcubes_baseline_maintenance(
        workspace,
        python_executable=python_executable,
        env=environment,
    )
    _record_phase(progress_path, "sugarcubes", "completed")
    _record_phase(progress_path, "model_root", "started")
    configure_backend_model_root(
        workspace=workspace,
        python_executable=python_executable,
        model_root=model_root,
    )
    _record_phase(progress_path, "model_root", "completed")
    _record_phase(progress_path, "validation", "started")
    validation = validate_managed_environment(
        workspace=workspace,
        expected_accelerator=AcceleratorClass.CPU,
    )
    if not validation.success:
        raise InstallerLifecycleError(validation.detail)
    _record_phase(progress_path, "validation", "completed")

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


def _record_phase(path: Path, phase: str, state: str) -> None:
    """Persist one flush-safe materialization boundary for timeout diagnostics."""

    path.parent.mkdir(parents=True, exist_ok=True)
    message = f"HISTORICAL_MATERIALIZATION phase={phase} state={state}"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")
        stream.flush()
    print(message, flush=True)


def _timeout_output(output: bytes | str | None) -> str:
    """Render captured timeout output without discarding byte diagnostics."""

    if output is None:
        return "<no output>"
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _argument_parser() -> argparse.ArgumentParser:
    """Build the private child-process command contract."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--endpoint-port", type=int, required=True)
    parser.add_argument("--managed-workspace", type=Path, required=True)
    parser.add_argument("--managed-model-root", type=Path, required=True)
    parser.add_argument("--source-repository", type=Path, required=True)
    return parser


def _main(arguments: list[str] | None = None) -> int:
    """Execute the private historical managed-configuration child command."""

    parsed = _argument_parser().parse_args(arguments)
    _materialize_historical_managed_configuration(
        repository_root=parsed.repository_root,
        install_root=parsed.install_root,
        endpoint_port=parsed.endpoint_port,
        managed_workspace=parsed.managed_workspace,
        managed_model_root=parsed.managed_model_root,
        source_repository=parsed.source_repository,
    )
    return 0


__all__ = ["materialize_historical_managed_configuration"]


if __name__ == "__main__":
    raise SystemExit(_main())
