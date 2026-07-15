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

"""Define installation, runtime, and Comfy target configuration models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import quote

from substitute.domain.onboarding.runtime_layout import runtime_layout_for_root


class ComfyTargetMode(str, Enum):
    """Identify the supported Comfy ownership and connection modes."""

    MANAGED_LOCAL = "managed_local"
    ATTACHED_LOCAL = "attached_local"
    REMOTE = "remote"


class RuntimeBootstrapStatus(str, Enum):
    """Describe the current Substitute runtime provisioning state."""

    MISSING = "missing"
    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class ComfyEndpoint:
    """Capture the HTTP and websocket endpoint used to reach Comfy."""

    host: str
    port: int

    def prompt_url(self) -> str:
        """Return the queue prompt endpoint URL."""

        return self._http_url("/prompt")

    def substitute_prompt_queue_url(self) -> str:
        """Return the Substitute BackEnd prompt queue facade URL."""

        return self._http_url("/substitute/v1/prompt/queue")

    def substitute_sugar_compile_url(self) -> str:
        """Return the Substitute BackEnd Sugar compile URL."""

        return self._http_url("/substitute/v1/sugar/compile")

    def substitute_capabilities_url(self) -> str:
        """Return the Substitute BackEnd capability endpoint URL."""

        return self._http_url("/substitute/v1/capabilities")

    def interrupt_url(self) -> str:
        """Return the interrupt endpoint URL."""

        return self._http_url("/interrupt")

    def queue_url(self) -> str:
        """Return the Comfy queue inspection and mutation endpoint URL."""

        return self._http_url("/queue")

    def history_url(self, prompt_id: str) -> str:
        """Return the Comfy history URL for one prompt identifier."""

        return self._http_url(f"/history/{quote(prompt_id, safe='')}")

    def upload_image_url(self) -> str:
        """Return the Comfy image upload endpoint URL."""

        return self._http_url("/upload/image")

    def view_url(self) -> str:
        """Return the Comfy artifact view endpoint URL."""

        return self._http_url("/view")

    def object_info_url(self, node_class: str) -> str:
        """Return the object-info URL for one node class."""

        return self._http_url(f"/object_info/{quote(node_class, safe='')}")

    def system_stats_url(self) -> str:
        """Return the Comfy system statistics endpoint URL."""

        return self._http_url("/system_stats")

    def logs_url(self) -> str:
        """Return the Comfy frontend logs endpoint URL when available."""

        return self._http_url("/internal/logs")

    def websocket_url(self, client_id: str) -> str:
        """Return the websocket URL for one client identifier."""

        return f"ws://{self.host}:{self.port}/ws?clientId={client_id}"

    def _http_url(self, path: str) -> str:
        """Return an HTTP URL rooted at this endpoint."""

        return f"http://{self.host}:{self.port}{path}"


@dataclass(frozen=True)
class InstallationConfiguration:
    """Capture visible installation-root paths owned by Substitute."""

    installation_root: Path
    user_dir: Path
    user_settings_dir: Path
    projects_dir: Path
    outputs_dir: Path
    sugar_scripts_dir: Path
    wildcards_dir: Path
    appdata_dir: Path
    session_dir: Path
    cache_dir: Path
    diagnostics_dir: Path
    logs_dir: Path
    runtime_state_dir: Path
    model_metadata_dir: Path
    runtime_dir: Path
    default_managed_comfy_dir: Path

    @classmethod
    def create_default(cls, installation_root: Path) -> InstallationConfiguration:
        """Build the default installation layout for one visible root."""

        resolved_root = installation_root.resolve()
        user_dir = resolved_root / "user"
        projects_dir = user_dir / "projects"
        appdata_dir = resolved_root / "appdata"
        cache_dir = appdata_dir / "cache"
        diagnostics_dir = appdata_dir / "diagnostics"
        return cls(
            installation_root=resolved_root,
            user_dir=user_dir,
            user_settings_dir=user_dir / "settings",
            projects_dir=projects_dir,
            outputs_dir=user_dir / "outputs",
            sugar_scripts_dir=projects_dir,
            wildcards_dir=user_dir / "wildcards",
            appdata_dir=appdata_dir,
            session_dir=appdata_dir / "session",
            cache_dir=cache_dir,
            diagnostics_dir=diagnostics_dir,
            logs_dir=diagnostics_dir / "logs",
            runtime_state_dir=appdata_dir / "runtime_state",
            model_metadata_dir=cache_dir / "model_metadata",
            runtime_dir=resolved_root / "runtime",
            default_managed_comfy_dir=resolved_root / "comfyui",
        )


@dataclass(frozen=True)
class RuntimeConfiguration:
    """Capture Substitute runtime provisioning state under the install root."""

    runtime_root: Path
    python_executable: Path | None
    bootstrap_status: RuntimeBootstrapStatus
    schema_version: str = "1"

    @classmethod
    def create_default(
        cls,
        installation: InstallationConfiguration,
    ) -> RuntimeConfiguration:
        """Build the default runtime configuration for one installation."""

        runtime_root = installation.runtime_dir
        python_executable = runtime_layout_for_root(runtime_root).python_executable
        return cls(
            runtime_root=runtime_root,
            python_executable=python_executable,
            bootstrap_status=RuntimeBootstrapStatus.MISSING,
        )


@dataclass(frozen=True)
class ComfyTargetConfiguration:
    """Capture the selected Comfy target and its ownership semantics."""

    mode: ComfyTargetMode
    endpoint: ComfyEndpoint
    workspace_path: Path | None
    install_owned: bool
    launch_owned: bool

    @classmethod
    def create_default(
        cls,
        installation: InstallationConfiguration,
    ) -> ComfyTargetConfiguration:
        """Build the default managed-local target for one installation."""

        return cls(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=installation.default_managed_comfy_dir,
            install_owned=True,
            launch_owned=True,
        )


@dataclass(frozen=True)
class InstallationContext:
    """Bundle the active installation, runtime, and target configuration state."""

    installation: InstallationConfiguration
    runtime: RuntimeConfiguration
    comfy_target: ComfyTargetConfiguration

    @property
    def install_root(self) -> Path:
        """Return the visible installation root path."""

        return self.installation.installation_root

    @property
    def projects_dir(self) -> Path:
        """Return the active projects root for this installation."""

        return self.installation.projects_dir

    @property
    def outputs_dir(self) -> Path:
        """Return the active generated-output root."""

        return self.installation.outputs_dir

    @property
    def sugar_scripts_dir(self) -> Path:
        """Return the active Sugar script recipe root."""

        return self.installation.sugar_scripts_dir

    @property
    def user_dir(self) -> Path:
        """Return the active Substitute user-data root."""

        return self.installation.user_dir

    @property
    def user_settings_dir(self) -> Path:
        """Return the active Substitute user settings root."""

        return self.installation.user_settings_dir

    @property
    def model_metadata_dir(self) -> Path:
        """Return the active model metadata cache root."""

        return self.installation.model_metadata_dir

    @property
    def wildcards_dir(self) -> Path:
        """Return the active Substitute-owned wildcard catalog root."""

        return self.installation.wildcards_dir

    @property
    def appdata_dir(self) -> Path:
        """Return the active Substitute app-owned data root."""

        return self.installation.appdata_dir

    @property
    def session_dir(self) -> Path:
        """Return the active session persistence root."""

        return self.installation.session_dir

    @property
    def cache_dir(self) -> Path:
        """Return the active app cache root."""

        return self.installation.cache_dir

    @property
    def diagnostics_dir(self) -> Path:
        """Return the active diagnostics root."""

        return self.installation.diagnostics_dir

    @property
    def logs_dir(self) -> Path:
        """Return the active diagnostics log root."""

        return self.installation.logs_dir

    @property
    def runtime_state_dir(self) -> Path:
        """Return the active managed runtime state root."""

        return self.installation.runtime_state_dir

    @property
    def active_comfy_custom_nodes_dir(self) -> Path | None:
        """Return the local active Comfy custom-node root when one exists."""

        if self.comfy_target.mode is ComfyTargetMode.REMOTE:
            return None
        workspace = self.comfy_target.workspace_path or self.managed_comfy_dir
        return workspace / "custom_nodes"

    @property
    def managed_comfy_dir(self) -> Path:
        """Return the default managed Comfy workspace directory."""

        return self.installation.default_managed_comfy_dir
