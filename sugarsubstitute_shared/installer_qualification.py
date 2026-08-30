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

"""Carry one authenticated release-qualification plan through process handoffs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Final, Literal, Mapping, TypeAlias


INSTALLER_QUALIFICATION_PLAN_ENV: Final = (
    "SUGAR_SUBSTITUTE_INSTALLER_QUALIFICATION_PLAN"
)
_SCHEMA_VERSION: Final = 3
_LEGACY_SCHEMA_VERSIONS: Final = frozenset({1, 2})
InstallerQualificationTarget: TypeAlias = Literal["managed_local", "remote"]


@dataclass(frozen=True, slots=True)
class InstallerQualificationPlan:
    """Describe one normal installer-to-main-shell qualification chain."""

    token: str
    install_root: Path
    endpoint_host: str
    endpoint_port: int
    event_log_path: Path
    timeout_seconds: float
    target_mode: InstallerQualificationTarget = "remote"
    managed_workspace_path: Path | None = None
    managed_model_root: Path | None = None
    force_cpu_mode: bool = False

    def to_json(self) -> str:
        """Serialize the plan for inheritance by installer child processes."""

        return json.dumps(
            {
                "schema_version": _SCHEMA_VERSION,
                "token": self.token,
                "install_root": str(self.install_root),
                "endpoint_host": self.endpoint_host,
                "endpoint_port": self.endpoint_port,
                "event_log_path": str(self.event_log_path),
                "timeout_seconds": self.timeout_seconds,
                "target_mode": self.target_mode,
                "managed_workspace_path": (
                    str(self.managed_workspace_path)
                    if self.managed_workspace_path is not None
                    else None
                ),
                "managed_model_root": (
                    str(self.managed_model_root)
                    if self.managed_model_root is not None
                    else None
                ),
                "force_cpu_mode": self.force_cpu_mode,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw_plan: str) -> InstallerQualificationPlan:
        """Parse and validate one inherited qualification plan."""

        payload = json.loads(raw_plan)
        if not isinstance(payload, dict):
            raise ValueError("Installer qualification plan must be a JSON object.")
        schema_version = payload.get("schema_version")
        if schema_version not in {*_LEGACY_SCHEMA_VERSIONS, _SCHEMA_VERSION}:
            raise ValueError("Installer qualification plan schema is unsupported.")
        token = payload.get("token")
        install_root = payload.get("install_root")
        endpoint_host = payload.get("endpoint_host")
        endpoint_port = payload.get("endpoint_port")
        event_log_path = payload.get("event_log_path")
        timeout_seconds = payload.get("timeout_seconds")
        target_mode = payload.get("target_mode", "remote")
        managed_workspace_path = payload.get("managed_workspace_path")
        managed_model_root = payload.get("managed_model_root")
        force_cpu_mode = payload.get("force_cpu_mode", False)
        if not isinstance(token, str) or not token:
            raise ValueError("Installer qualification token is missing.")
        if not isinstance(install_root, str) or not install_root:
            raise ValueError("Installer qualification install root is missing.")
        if not isinstance(endpoint_host, str) or not endpoint_host:
            raise ValueError("Installer qualification endpoint host is missing.")
        if not isinstance(endpoint_port, int) or not 1 <= endpoint_port <= 65_535:
            raise ValueError("Installer qualification endpoint port is invalid.")
        if not isinstance(event_log_path, str) or not event_log_path:
            raise ValueError("Installer qualification event log path is missing.")
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise ValueError("Installer qualification timeout is invalid.")
        if target_mode not in {"managed_local", "remote"}:
            raise ValueError("Installer qualification target mode is invalid.")
        if managed_workspace_path is not None and not isinstance(
            managed_workspace_path, str
        ):
            raise ValueError("Installer qualification managed workspace is invalid.")
        if managed_model_root is not None and not isinstance(managed_model_root, str):
            raise ValueError("Installer qualification managed model root is invalid.")
        if not isinstance(force_cpu_mode, bool):
            raise ValueError("Installer qualification CPU preference is invalid.")
        if target_mode == "managed_local" and not managed_workspace_path:
            raise ValueError("Managed qualification requires a workspace path.")
        return cls(
            token=token,
            install_root=Path(install_root).resolve(),
            endpoint_host=endpoint_host,
            endpoint_port=endpoint_port,
            event_log_path=Path(event_log_path).resolve(),
            timeout_seconds=float(timeout_seconds),
            target_mode=target_mode,
            managed_workspace_path=(
                Path(managed_workspace_path).resolve()
                if managed_workspace_path is not None
                else None
            ),
            managed_model_root=(
                Path(managed_model_root).resolve()
                if managed_model_root is not None
                else None
            ),
            force_cpu_mode=force_cpu_mode,
        )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> InstallerQualificationPlan | None:
        """Return the inherited plan when qualification was explicitly requested."""

        source = os.environ if environment is None else environment
        raw_plan = source.get(INSTALLER_QUALIFICATION_PLAN_ENV)
        if raw_plan is None:
            return None
        return cls.from_json(raw_plan)

    def record(self, event: str, **fields: object) -> None:
        """Append one token-bound event to the cross-process qualification log."""

        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "token": self.token,
            "event": event,
            "pid": os.getpid(),
            "fields": fields,
        }
        with self.event_log_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(payload, sort_keys=True) + "\n")


__all__ = [
    "INSTALLER_QUALIFICATION_PLAN_ENV",
    "InstallerQualificationPlan",
    "InstallerQualificationTarget",
]
