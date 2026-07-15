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

"""Run Comfy Manager commands through Comfy CLI inside one workspace."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import os
from pathlib import Path

from substitute.infrastructure.comfy.nodepack_manifest import (
    CLI_INSTALL_TIMEOUT_SECONDS,
)
from substitute.infrastructure.process.hidden_process_runner import (
    run_command,
    stream_command,
    stream_command_collecting_output,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger(__name__)


class ComfyCliWorkspaceAdapter:
    """Run Comfy CLI commands inside the selected Comfy workspace runtime."""

    def __init__(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the adapter with explicit workspace ownership."""

        self._workspace = workspace
        self._python_executable = python_executable
        self._on_log = on_log
        self._env = comfy_cli_environment(workspace=workspace, env=env)

    def ensure_available(self) -> None:
        """Install comfy-cli into the workspace runtime when it is missing."""

        result = run_command(
            [str(self._python_executable), "-c", "import comfy_cli"],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode == 0:
            return
        _emit_log(self._on_log, "[ComfyCLI] Installing comfy-cli into ComfyUI.")
        exit_code = stream_command(
            [str(self._python_executable), "-m", "pip", "install", "comfy-cli"],
            cwd=self._workspace,
            on_line=self._on_log,
            env=self._env,
        )
        if exit_code != 0:
            raise RuntimeError("Substitute could not install comfy-cli into ComfyUI.")

    @property
    def workspace(self) -> Path:
        """Return the Comfy workspace this adapter manages."""

        return self._workspace

    def manager_knows_node(self, node_id: str) -> bool:
        """Return whether Comfy Manager can resolve a custom-node install id."""

        result = run_command(
            [
                str(self._python_executable),
                "-m",
                "cm_cli",
                "show",
                "not-installed",
            ],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode != 0:
            _emit_log(
                self._on_log,
                (
                    "[ComfyNodepacks] Could not inspect Comfy Manager node list; "
                    "using source fallback when available."
                ),
            )
            return False
        return manager_show_output_contains_node(result.stdout, node_id)

    def install_node(self, node_id: str) -> None:
        """Install one Comfy Registry node id through Comfy CLI."""

        command = [
            str(self._python_executable),
            "-m",
            "cm_cli",
            "install",
            "--exit-on-fail",
            node_id,
        ]
        exit_code, output_lines = stream_command_collecting_output(
            command,
            cwd=self._workspace,
            on_line=self._on_log,
            timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
            env=self._env,
        )
        if exit_code != 0 or comfy_manager_install_output_failed(output_lines):
            raise RuntimeError(comfy_cli_install_failure_message(node_id, output_lines))

    def restore_dependencies(self) -> None:
        """Install dependencies for installed custom nodes through Comfy Manager."""

        _emit_log(
            self._on_log,
            "[ComfyCLI] Restoring installed custom-node dependencies.",
        )
        command = [
            str(self._python_executable),
            "-m",
            "cm_cli",
            "restore-dependencies",
        ]
        exit_code, output_lines = stream_command_collecting_output(
            command,
            cwd=self._workspace,
            on_line=self._on_log,
            timeout_seconds=CLI_INSTALL_TIMEOUT_SECONDS,
            env=self._env,
        )
        if exit_code != 0 or comfy_manager_install_output_failed(output_lines):
            raise RuntimeError(
                comfy_cli_install_failure_message(
                    "installed custom-node dependencies",
                    output_lines,
                )
            )

    def clear_startup_actions(self) -> None:
        """Clear Manager startup actions already handled during setup."""

        result = run_command(
            [str(self._python_executable), "-m", "cm_cli", "clear"],
            cwd=self._workspace,
            check=False,
            env=self._env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Comfy CLI could not clear Comfy Manager startup actions."
            )


def manager_show_output_contains_node(output: str, node_id: str) -> bool:
    """Return whether Comfy Manager show output contains a node id token."""

    normalized_node_id = node_id.casefold()
    for line in output.splitlines():
        tokens = {
            token.strip(" │|[](){}<>,;:'\"").casefold()
            for token in line.split()
            if token.strip()
        }
        if normalized_node_id in tokens:
            return True
    return False


def comfy_manager_install_output_failed(output_lines: Sequence[str]) -> bool:
    """Return whether Comfy Manager printed a failed install despite exit code zero."""

    for line in output_lines:
        normalized = line.strip().casefold()
        if normalized.startswith("error:"):
            return True
        if "[failed]" in normalized:
            return True
    return False


def comfy_cli_install_failure_message(
    node_id: str,
    output_lines: Sequence[str],
) -> str:
    """Return an actionable Comfy Manager install failure message."""

    relevant_lines = [
        line.strip()
        for line in output_lines
        if line.strip()
        and (
            line.strip().casefold().startswith("error:")
            or "not found" in line.casefold()
            or "failed" in line.casefold()
        )
    ]
    excerpt = " ".join(
        relevant_lines[-4:] or [line.strip() for line in output_lines[-4:]]
    )
    if excerpt:
        return f"Comfy CLI could not install required node '{node_id}'. {excerpt}"
    return f"Comfy CLI could not install required node '{node_id}'."


def comfy_cli_environment(
    *,
    workspace: Path,
    env: Mapping[str, str] | None,
) -> dict[str, str]:
    """Build the subprocess environment required by comfy-cli and Manager."""

    command_env = dict(os.environ if env is None else env)
    command_env["COMFYUI_PATH"] = str(workspace)
    command_env.setdefault("PYTHONUTF8", "1")
    command_env.setdefault("PYTHONIOENCODING", "utf-8:replace")
    return command_env


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one Comfy CLI adapter line to logs and optional setup output."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "ComfyCliWorkspaceAdapter",
    "LogCallback",
    "comfy_cli_environment",
    "comfy_cli_install_failure_message",
    "comfy_manager_install_output_failed",
    "manager_show_output_contains_node",
]
