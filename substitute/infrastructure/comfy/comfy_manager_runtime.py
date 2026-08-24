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

"""Own every protected Comfy Manager CLI command and process environment."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.manager_environment import (
    manager_runtime_environment,
)
from substitute.infrastructure.process.hidden_process_runner import (
    run_command,
    stream_command_collecting_output,
)
from sugarsubstitute_shared.windows_long_paths import subprocess_path

LogCallback = Callable[[str], None]


def selected_comfy_environment(
    *,
    runtime: ComfyManagerRuntime,
    env: Mapping[str, str] | None,
) -> dict[str, str]:
    """Bind CLI work to one validated Manager runtime without system Git."""

    selected_env = manager_runtime_environment(
        runtime.workspace,
        env,
        use_pygit2=runtime.uses_pygit2,
    )
    selected_env.pop("CONDA_PREFIX", None)
    selected_env["COMFYUI_FOLDERS_BASE_PATH"] = str(runtime.workspace.resolve())
    executable_directory = runtime.python_executable.resolve().parent
    if executable_directory.name.casefold() in {"scripts", "bin"}:
        selected_env["VIRTUAL_ENV"] = str(executable_directory.parent)
    else:
        selected_env.pop("VIRTUAL_ENV", None)
    return selected_env


class ComfyManagerCommandRunner:
    """Run supported ComfyCLI operations through one protected boundary."""

    def __init__(
        self,
        *,
        runtime: ComfyManagerRuntime,
        env: Mapping[str, str] | None,
    ) -> None:
        """Capture the validated runtime and caller's base environment."""

        self._runtime = runtime
        self._environment = selected_comfy_environment(runtime=runtime, env=env)

    def install_registry_nodepack(
        self,
        *,
        node_spec: str,
        on_line: LogCallback | None,
        timeout_seconds: int,
    ) -> tuple[int, tuple[str, ...]] | None:
        """Install one exact Registry nodepack through the available ComfyCLI."""

        command = self._registry_install_command(node_spec)
        if command is None:
            return None
        return stream_command_collecting_output(
            command,
            cwd=self._runtime.workspace,
            on_line=on_line,
            timeout_seconds=timeout_seconds,
            env=self._environment,
        )

    def settle_registry_updates(
        self,
        *,
        session_path: Path,
        on_line: LogCallback | None,
        timeout_seconds: int,
    ) -> tuple[int, tuple[str, ...]] | None:
        """Run Manager's pre-startup executor for queued Registry updates."""

        if not self._module_available("comfyui_manager.prestartup_script"):
            return None
        environment = dict(self._environment)
        environment["__COMFY_CLI_SESSION__"] = str(session_path)
        return stream_command_collecting_output(
            [
                subprocess_path(self._runtime.python_executable),
                "-m",
                "comfyui_manager.prestartup_script",
            ],
            cwd=self._runtime.workspace,
            on_line=on_line,
            timeout_seconds=timeout_seconds,
            env=environment,
        )

    def _registry_install_command(self, node_spec: str) -> list[str] | None:
        """Select the supported command exposed by the validated runtime."""

        python = subprocess_path(self._runtime.python_executable)
        workspace = subprocess_path(self._runtime.workspace)
        if self._module_available("comfy_cli"):
            return [
                python,
                "-m",
                "comfy_cli",
                "--workspace",
                workspace,
                "--skip-prompt",
                "node",
                "install",
                "--exit-on-fail",
                "--no-deps",
                node_spec,
                "--mode",
                "remote",
            ]
        if self._module_available("cm_cli"):
            return [
                python,
                "-m",
                "cm_cli",
                "install",
                "--exit-on-fail",
                "--no-deps",
                node_spec,
                "--mode",
                "remote",
            ]
        if (
            self._runtime.kind is ComfyManagerKind.LEGACY_CUSTOM_NODE
            and self._runtime.legacy_cli_path is not None
            and self._runtime.legacy_cli_path.is_file()
        ):
            return [
                python,
                subprocess_path(self._runtime.legacy_cli_path),
                "install",
                "--no-deps",
                node_spec,
                "--mode",
                "remote",
            ]
        return None

    def _module_available(self, module_name: str) -> bool:
        """Return whether the selected Comfy Python exposes one module."""

        probe = run_command(
            [
                subprocess_path(self._runtime.python_executable),
                "-c",
                (
                    "import importlib.util; "
                    f"raise SystemExit(importlib.util.find_spec({module_name!r}) is None)"
                ),
            ],
            cwd=self._runtime.workspace,
            check=False,
            env=self._environment,
        )
        return probe.returncode == 0


__all__ = ["ComfyManagerCommandRunner", "selected_comfy_environment"]
