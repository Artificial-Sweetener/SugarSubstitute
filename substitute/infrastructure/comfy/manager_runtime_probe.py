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

"""Probe Manager runtimes without mutating their ComfyUI workspace."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import subprocess
from typing import Final, cast

from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy.manager_contract import ComfyManagerContract
from substitute.infrastructure.comfy.manager_environment import (
    manager_environment,
    manager_runtime_environment,
)
from substitute.infrastructure.comfy.workspace_python_resolver import (
    resolve_workspace_python,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)

_LOGGER = get_logger("infrastructure.comfy.manager_runtime_probe")
_PROBE_MARKER: Final[str] = "SUGARSUBSTITUTE_MANAGER_PROBE="
_INTEGRATED_PROBE_SCRIPT: Final[str] = (
    "import importlib.metadata, json; from pathlib import Path; "
    "import comfyui_manager; "
    "package_file = getattr(comfyui_manager, '__file__', None); "
    "assert package_file and Path(package_file).name == '__init__.py'; "
    "package_root = Path(package_file).resolve().parent; "
    "payload = {'version': importlib.metadata.version('comfyui-manager'), "
    "'supports_pygit2': (package_root / 'common' / 'git_compat.py').is_file()}; "
    f"print('{_PROBE_MARKER}' + json.dumps(payload, sort_keys=True))"
)
_PYGIT2_PROBE_SCRIPT: Final[str] = (
    "import json; from comfyui_manager.common import git_compat; "
    "assert git_compat.USE_PYGIT2, 'Integrated Manager did not select pygit2'; "
    f"print('{_PROBE_MARKER}' + json.dumps({{'uses_pygit2': True}}))"
)


@dataclass(frozen=True, slots=True)
class ComfyManagerProbeResult:
    """Preserve a validated runtime or its actionable probe failure."""

    runtime: ComfyManagerRuntime | None
    failure: str = ""


class ComfyManagerRuntimeProbe:
    """Run bounded, hidden probes for integrated and legacy Manager runtimes."""

    def integrated(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Probe the integrated package and discover optional capabilities."""

        contract = ComfyManagerContract(workspace)
        if not contract.supports_integrated_manager:
            return ComfyManagerProbeResult(
                None,
                "ComfyUI does not declare integrated Manager support.",
            )
        result = self._run(
            [subprocess_path(python_executable), "-c", _INTEGRATED_PROBE_SCRIPT],
            workspace=workspace,
            env=manager_runtime_environment(
                workspace,
                env,
                use_pygit2=False,
            ),
        )
        if result.returncode != 0:
            return ComfyManagerProbeResult(None, command_output(result))
        payload = _probe_payload(result)
        if payload is None:
            return ComfyManagerProbeResult(
                None,
                "Integrated Manager returned no valid probe record. "
                + command_output(result),
            )
        version = payload.get("version")
        supports_pygit2 = payload.get("supports_pygit2")
        if not isinstance(version, str) or not isinstance(supports_pygit2, bool):
            return ComfyManagerProbeResult(
                None,
                "Integrated Manager returned incomplete probe data.",
            )
        runtime = ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python_executable,
            version=version,
            supports_pygit2=supports_pygit2,
        )
        log_info(
            _LOGGER,
            "Detected integrated ComfyUI Manager runtime",
            version=version,
            supports_pygit2=supports_pygit2,
        )
        return ComfyManagerProbeResult(runtime)

    def pygit2_backend(
        self,
        runtime: ComfyManagerRuntime,
        *,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Validate and select the optional integrated pygit2 backend."""

        if runtime.kind is not ComfyManagerKind.INTEGRATED:
            return ComfyManagerProbeResult(
                None, "Legacy Manager has no pygit2 backend."
            )
        if not runtime.supports_pygit2:
            return ComfyManagerProbeResult(runtime)
        result = self._run(
            [
                subprocess_path(runtime.python_executable),
                "-c",
                _PYGIT2_PROBE_SCRIPT,
            ],
            workspace=runtime.workspace,
            env=manager_runtime_environment(
                runtime.workspace,
                env,
                use_pygit2=True,
            ),
        )
        if result.returncode != 0:
            return ComfyManagerProbeResult(None, command_output(result))
        payload = _probe_payload(result)
        if payload is None or payload.get("uses_pygit2") is not True:
            return ComfyManagerProbeResult(
                None,
                "Integrated Manager did not confirm its pygit2 backend.",
            )
        selected = replace(runtime, uses_pygit2=True)
        log_info(
            _LOGGER,
            "Validated integrated ComfyUI Manager pygit2 backend",
            version=runtime.version,
        )
        return ComfyManagerProbeResult(selected)

    def legacy(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> ComfyManagerProbeResult:
        """Probe the legacy Manager custom-node CLI."""

        cli_path = ComfyManagerContract(workspace).legacy_cli_path
        if not cli_path.is_file():
            return ComfyManagerProbeResult(
                None,
                f"Legacy Manager CLI is missing: {cli_path}",
            )
        result = self._run(
            [
                subprocess_path(python_executable),
                subprocess_path(cli_path),
                "--help",
            ],
            workspace=workspace,
            env=manager_environment(workspace, env),
        )
        if result.returncode != 0:
            return ComfyManagerProbeResult(None, command_output(result))
        return ComfyManagerProbeResult(
            ComfyManagerRuntime(
                kind=ComfyManagerKind.LEGACY_CUSTOM_NODE,
                workspace=workspace,
                python_executable=python_executable,
                legacy_cli_path=cli_path,
            )
        )

    def _run(
        self,
        command: list[str],
        *,
        workspace: Path,
        env: Mapping[str, str],
    ) -> subprocess.CompletedProcess[str]:
        """Run one timeout-bounded probe without creating a visible window."""

        return subprocess.run(
            command,
            cwd=subprocess_working_directory(workspace),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )


def detect_workspace_manager_runtime(
    workspace: Path,
    *,
    python_executable: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ComfyManagerRuntime:
    """Return the preferred validated Manager runtime without mutation."""

    resolved_python = python_executable or resolve_workspace_python(workspace)
    probe = ComfyManagerRuntimeProbe()
    integrated = probe.integrated(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if integrated.runtime is not None:
        if integrated.runtime.supports_pygit2:
            pygit2 = probe.pygit2_backend(integrated.runtime, env=env)
            if pygit2.runtime is not None:
                return pygit2.runtime
            log_warning(
                _LOGGER,
                "Integrated Manager pygit2 backend is unavailable during detection",
                version=integrated.runtime.version,
                error=pygit2.failure,
            )
        return integrated.runtime
    legacy = probe.legacy(
        workspace=workspace,
        python_executable=resolved_python,
        env=env,
    )
    if legacy.runtime is not None:
        return legacy.runtime
    detail = integrated.failure or legacy.failure
    raise RuntimeError(validation_failure_message("workspace", detail))


def validation_failure_message(kind: str, detail: str) -> str:
    """Build an actionable Manager validation failure message."""

    excerpt = detail.strip() or "The validation command returned no diagnostic output."
    return f"ComfyUI Manager {kind} validation failed. {excerpt}"


def command_output(result: subprocess.CompletedProcess[str]) -> str:
    """Return a bounded combined stdout/stderr diagnostic excerpt."""

    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    return " ".join(lines[-20:])[-4_000:]


def _probe_payload(
    result: subprocess.CompletedProcess[str],
) -> dict[str, object] | None:
    """Return the final marker-prefixed JSON object from probe output."""

    for line in reversed((result.stdout or "").splitlines()):
        if not line.startswith(_PROBE_MARKER):
            continue
        try:
            payload = json.loads(line.removeprefix(_PROBE_MARKER))
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return cast("dict[str, object]", payload)
        return None
    return None


__all__ = [
    "ComfyManagerProbeResult",
    "ComfyManagerRuntimeProbe",
    "command_output",
    "detect_workspace_manager_runtime",
    "validation_failure_message",
]
