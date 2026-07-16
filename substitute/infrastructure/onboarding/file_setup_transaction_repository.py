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

"""Persist pending setup transactions under the install state root."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import tempfile
from typing import Any

from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepository,
    SetupTransactionRepositoryError,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding.comfy_python_models import (
    ComfyPythonBinding,
    ComfyPythonSelectionSource,
)
from substitute.domain.onboarding.models import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.onboarding.file_setup_transaction_repository")
_SCHEMA_VERSION = 1


@dataclass
class FileSetupTransactionRepository(SetupTransactionRepository):
    """Read and write `setup_transaction.json` under app runtime state storage."""

    runtime_state_dir: Path

    def exists(self) -> bool:
        """Return whether persisted pending setup state exists."""

        return self._path().exists()

    def load(self) -> SetupTransaction | None:
        """Load pending setup state and report corrupt payloads explicitly."""

        path = self._path()
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Setup transaction payload must be a JSON object.")
            return _transaction_from_payload(payload)
        except Exception as error:
            log_warning(
                _LOGGER,
                "Pending setup transaction could not be read.",
                path=path,
                error=error,
            )
            raise SetupTransactionRepositoryError(
                f"Pending setup transaction is invalid: {path}"
            ) from error

    def save(self, transaction: SetupTransaction) -> None:
        """Persist one pending setup transaction through same-directory replace."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            _transaction_to_payload(transaction),
            indent=2,
        )
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
        ) as file:
            file.write(payload)
            file.flush()
            temporary_path = Path(file.name)
        temporary_path.replace(path)

    def delete(self) -> None:
        """Remove the pending setup transaction when present."""

        path = self._path()
        if path.exists():
            path.unlink()

    def _path(self) -> Path:
        """Return the pending setup transaction path."""

        return self.runtime_state_dir / "setup_transaction.json"


def _transaction_to_payload(transaction: SetupTransaction) -> dict[str, Any]:
    """Serialize one setup transaction to a JSON-compatible payload."""

    return {
        "schema_version": transaction.schema_version,
        "transaction_id": transaction.transaction_id,
        "mode": transaction.mode.value,
        "status": transaction.status.value,
        "created_at": transaction.created_at.isoformat(),
        "updated_at": transaction.updated_at.isoformat(),
        "installation": _installation_to_payload(transaction.installation),
        "runtime": _runtime_to_payload(transaction.runtime),
        "target": _target_to_payload(transaction.target),
        "managed_runtime": _managed_runtime_to_payload(transaction.managed_runtime),
        "workspace_path": _path_to_string(transaction.workspace_path),
        "endpoint_host": transaction.endpoint_host,
        "endpoint_port": transaction.endpoint_port,
        "force_cpu_mode": transaction.force_cpu_mode,
        "prefer_edge_torch": transaction.prefer_edge_torch,
        "prefer_edge_comfy_channel": transaction.prefer_edge_comfy_channel,
        "failure": _failure_to_payload(transaction.failure),
    }


def _transaction_from_payload(payload: dict[str, Any]) -> SetupTransaction:
    """Deserialize one JSON payload into a setup transaction."""

    schema_version = int(payload.get("schema_version", 0))
    if schema_version != _SCHEMA_VERSION:
        raise ValueError(f"Unsupported setup transaction schema: {schema_version}")
    return SetupTransaction(
        schema_version=schema_version,
        transaction_id=str(payload["transaction_id"]),
        mode=SetupTransactionMode(str(payload["mode"])),
        status=SetupTransactionStatus(str(payload["status"])),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        installation=_installation_from_payload(payload.get("installation")),
        runtime=_runtime_from_payload(payload.get("runtime")),
        target=_target_from_payload(payload.get("target")),
        managed_runtime=_managed_runtime_from_payload(payload.get("managed_runtime")),
        workspace_path=_path_from_value(payload.get("workspace_path")),
        endpoint_host=_optional_string(payload.get("endpoint_host")),
        endpoint_port=_optional_int(payload.get("endpoint_port")),
        force_cpu_mode=bool(payload.get("force_cpu_mode", False)),
        prefer_edge_torch=bool(payload.get("prefer_edge_torch", False)),
        prefer_edge_comfy_channel=bool(payload.get("prefer_edge_comfy_channel", False)),
        failure=_failure_from_payload(payload.get("failure")),
    )


def _installation_to_payload(
    configuration: InstallationConfiguration | None,
) -> dict[str, str] | None:
    """Serialize installation configuration when present."""

    if configuration is None:
        return None
    return {
        "installation_root": str(configuration.installation_root),
        "user_dir": str(configuration.user_dir),
        "user_settings_dir": str(configuration.user_settings_dir),
        "projects_dir": str(configuration.projects_dir),
        "outputs_dir": str(configuration.outputs_dir),
        "sugar_scripts_dir": str(configuration.projects_dir),
        "wildcards_dir": str(configuration.wildcards_dir),
        "appdata_dir": str(configuration.appdata_dir),
        "session_dir": str(configuration.session_dir),
        "cache_dir": str(configuration.cache_dir),
        "diagnostics_dir": str(configuration.diagnostics_dir),
        "logs_dir": str(configuration.logs_dir),
        "runtime_state_dir": str(configuration.runtime_state_dir),
        "model_metadata_dir": str(configuration.model_metadata_dir),
        "runtime_dir": str(configuration.runtime_dir),
        "default_managed_comfy_dir": str(configuration.default_managed_comfy_dir),
    }


def _installation_from_payload(payload: object) -> InstallationConfiguration | None:
    """Deserialize installation configuration when present."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Installation payload must be a JSON object.")
    installation_root = Path(str(payload["installation_root"]))
    defaults = InstallationConfiguration.create_default(installation_root)
    user_dir = Path(str(payload.get("user_dir", defaults.user_dir)))
    legacy_payload = any(
        key in payload
        for key in (
            "config_dir",
            "state_dir",
            "cubes_dir",
            "workspace_custom_nodes_dir",
        )
    )

    def appdata_path(key: str, default_path: Path) -> Path:
        """Return app-data owned paths normalized away from legacy locations."""

        if legacy_payload:
            return default_path
        return Path(str(payload.get(key, default_path)))

    projects_dir = Path(str(payload.get("projects_dir", defaults.projects_dir)))
    return InstallationConfiguration(
        installation_root=installation_root,
        user_dir=user_dir,
        user_settings_dir=Path(
            str(payload.get("user_settings_dir", defaults.user_settings_dir))
        ),
        projects_dir=projects_dir,
        outputs_dir=Path(str(payload.get("outputs_dir", user_dir / "outputs"))),
        sugar_scripts_dir=projects_dir,
        wildcards_dir=Path(str(payload.get("wildcards_dir", user_dir / "wildcards"))),
        appdata_dir=appdata_path("appdata_dir", defaults.appdata_dir),
        session_dir=appdata_path("session_dir", defaults.session_dir),
        cache_dir=appdata_path("cache_dir", defaults.cache_dir),
        diagnostics_dir=appdata_path("diagnostics_dir", defaults.diagnostics_dir),
        logs_dir=appdata_path("logs_dir", defaults.logs_dir),
        runtime_state_dir=appdata_path("runtime_state_dir", defaults.runtime_state_dir),
        model_metadata_dir=appdata_path(
            "model_metadata_dir", defaults.model_metadata_dir
        ),
        runtime_dir=Path(str(payload.get("runtime_dir", defaults.runtime_dir))),
        default_managed_comfy_dir=Path(
            str(
                payload.get(
                    "default_managed_comfy_dir",
                    defaults.default_managed_comfy_dir,
                )
            )
        ),
    )


def _runtime_to_payload(
    configuration: RuntimeConfiguration | None,
) -> dict[str, str | None] | None:
    """Serialize runtime configuration when present."""

    if configuration is None:
        return None
    return {
        "runtime_root": str(configuration.runtime_root),
        "python_executable": _path_to_string(configuration.python_executable),
        "bootstrap_status": configuration.bootstrap_status.value,
        "schema_version": configuration.schema_version,
    }


def _runtime_from_payload(payload: object) -> RuntimeConfiguration | None:
    """Deserialize runtime configuration when present."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Runtime payload must be a JSON object.")
    python_executable = payload.get("python_executable")
    return RuntimeConfiguration(
        runtime_root=Path(str(payload["runtime_root"])),
        python_executable=Path(str(python_executable))
        if isinstance(python_executable, str)
        else None,
        bootstrap_status=RuntimeBootstrapStatus(str(payload["bootstrap_status"])),
        schema_version=str(payload.get("schema_version", "1")),
    )


def _target_to_payload(
    configuration: ComfyTargetConfiguration | None,
) -> dict[str, object] | None:
    """Serialize Comfy target configuration when present."""

    if configuration is None:
        return None
    return {
        "mode": configuration.mode.value,
        "endpoint": {
            "host": configuration.endpoint.host,
            "port": configuration.endpoint.port,
        },
        "workspace_path": _path_to_string(configuration.workspace_path),
        "install_owned": configuration.install_owned,
        "launch_owned": configuration.launch_owned,
        "python_binding": _python_binding_to_payload(configuration.python_binding),
    }


def _target_from_payload(payload: object) -> ComfyTargetConfiguration | None:
    """Deserialize Comfy target configuration when present."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Target payload must be a JSON object.")
    endpoint_payload = payload.get("endpoint")
    if not isinstance(endpoint_payload, dict):
        raise ValueError("Target endpoint payload must be a JSON object.")
    workspace_path = payload.get("workspace_path")
    return ComfyTargetConfiguration(
        mode=ComfyTargetMode(str(payload["mode"])),
        endpoint=ComfyEndpoint(
            host=str(endpoint_payload["host"]),
            port=int(endpoint_payload["port"]),
        ),
        workspace_path=Path(str(workspace_path))
        if isinstance(workspace_path, str)
        else None,
        install_owned=bool(payload.get("install_owned", False)),
        launch_owned=bool(payload.get("launch_owned", False)),
        python_binding=_python_binding_from_payload(payload.get("python_binding")),
    )


def _python_binding_to_payload(
    binding: ComfyPythonBinding | None,
) -> dict[str, str] | None:
    """Serialize optional verified Comfy Python evidence."""

    if binding is None:
        return None
    return {
        "executable": str(binding.executable),
        "version": binding.version,
        "architecture": binding.architecture,
        "prefix": str(binding.prefix),
        "base_prefix": str(binding.base_prefix),
        "source": binding.source.value,
    }


def _python_binding_from_payload(payload: object) -> ComfyPythonBinding | None:
    """Deserialize optional verified Comfy Python evidence."""

    if not isinstance(payload, dict):
        return None
    return ComfyPythonBinding(
        executable=Path(str(payload["executable"])),
        version=str(payload["version"]),
        architecture=str(payload["architecture"]),
        prefix=Path(str(payload["prefix"])),
        base_prefix=Path(str(payload["base_prefix"])),
        source=ComfyPythonSelectionSource(str(payload["source"])),
    )


def _managed_runtime_to_payload(
    configuration: ManagedRuntimeConfiguration | None,
) -> dict[str, object] | None:
    """Serialize managed runtime configuration when present."""

    if configuration is None:
        return None
    return {
        "workspace_path": configuration.workspace_path,
        "detected_platform": configuration.detected_platform,
        "detected_accelerator": configuration.detected_accelerator,
        "detected_adapter_name": configuration.detected_adapter_name,
        "install_target": configuration.install_target,
        "python_version": configuration.python_version,
        "python_fallback_used": configuration.python_fallback_used,
        "comfy_channel": configuration.comfy_channel,
        "backend_policy": configuration.backend_policy,
        "torch_release_channel": configuration.torch_release_channel,
        "torch_selection_reason": configuration.torch_selection_reason,
        "torch_fallback_used": configuration.torch_fallback_used,
        "stability": configuration.stability.value,
        "prefer_edge_torch": configuration.prefer_edge_torch,
        "prefer_edge_comfy_channel": configuration.prefer_edge_comfy_channel,
        "force_cpu_mode": configuration.force_cpu_mode,
        "validation_status": configuration.validation_status.value,
        "validation_detail": configuration.validation_detail,
        "last_validation_at": configuration.last_validation_at,
        "launch_status": configuration.launch_status.value,
        "launch_detail": configuration.launch_detail,
        "last_launch_at": configuration.last_launch_at,
    }


def _managed_runtime_from_payload(
    payload: object,
) -> ManagedRuntimeConfiguration | None:
    """Deserialize managed runtime configuration when present."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Managed runtime payload must be a JSON object.")
    return ManagedRuntimeConfiguration(
        workspace_path=_optional_string(payload.get("workspace_path")),
        detected_platform=_optional_string(payload.get("detected_platform")),
        detected_accelerator=_optional_string(payload.get("detected_accelerator")),
        detected_adapter_name=_optional_string(payload.get("detected_adapter_name")),
        install_target=_optional_string(payload.get("install_target")),
        python_version=_optional_string(payload.get("python_version")),
        python_fallback_used=bool(payload.get("python_fallback_used", False)),
        comfy_channel=_optional_string(payload.get("comfy_channel")),
        backend_policy=_optional_string(payload.get("backend_policy")),
        torch_release_channel=_optional_string(payload.get("torch_release_channel")),
        torch_selection_reason=_optional_string(payload.get("torch_selection_reason")),
        torch_fallback_used=bool(payload.get("torch_fallback_used", False)),
        stability=ManagedRuntimeStability(str(payload.get("stability", "stable"))),
        prefer_edge_torch=bool(payload.get("prefer_edge_torch", False)),
        prefer_edge_comfy_channel=bool(payload.get("prefer_edge_comfy_channel", False)),
        force_cpu_mode=bool(payload.get("force_cpu_mode", False)),
        validation_status=ManagedRuntimeValidationStatus(
            str(payload.get("validation_status", "unknown"))
        ),
        validation_detail=_optional_string(payload.get("validation_detail")),
        last_validation_at=_optional_string(payload.get("last_validation_at")),
        launch_status=ManagedRuntimeLaunchStatus(
            str(payload.get("launch_status", "unknown"))
        ),
        launch_detail=_optional_string(payload.get("launch_detail")),
        last_launch_at=_optional_string(payload.get("last_launch_at")),
    )


def _failure_to_payload(
    failure: SetupTransactionFailure | None,
) -> dict[str, object] | None:
    """Serialize setup failure details when present."""

    if failure is None:
        return None
    return {
        "code": failure.code,
        "message": failure.message,
        "recoverable": failure.recoverable,
        "diagnostic_detail": failure.diagnostic_detail,
    }


def _failure_from_payload(payload: object) -> SetupTransactionFailure | None:
    """Deserialize setup failure details when present."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Failure payload must be a JSON object.")
    return SetupTransactionFailure(
        code=str(payload["code"]),
        message=str(payload["message"]),
        recoverable=bool(payload["recoverable"]),
        diagnostic_detail=_optional_string(payload.get("diagnostic_detail")),
    )


def _path_to_string(path: Path | None) -> str | None:
    """Return one path as a string when present."""

    return str(path) if path is not None else None


def _path_from_value(value: object) -> Path | None:
    """Return one optional path from a serialized value."""

    return Path(value) if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    """Return one optional integer from a serialized value."""

    if value is None:
        return None
    if isinstance(value, (str, int)):
        return int(value)
    raise ValueError("Expected optional integer payload value.")


def _optional_string(value: object) -> str | None:
    """Normalize one optional string payload value."""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


__all__ = ["FileSetupTransactionRepository"]
