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

"""Probe and select a verified Python binding for a stopped Comfy workspace."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Final

from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonResolutionError,
    ComfyPythonResolutionFailure,
    ComfyPythonSelectionSource,
)
from substitute.infrastructure.comfy.managed_validation import workspace_python_path
from substitute.infrastructure.comfy.workspace_python_resolver import (
    attached_comfy_python_candidates,
)

_PROBE_TIMEOUT_SECONDS: Final[float] = 8.0
_REQUIRED_MODULES: Final[tuple[str, ...]] = ("comfy", "torch", "aiohttp")
_PROBE_SCRIPT: Final[str] = """
import importlib.util, json, platform, sys
required = ("comfy", "torch", "aiohttp")
print(json.dumps({"executable": sys.executable, "prefix": sys.prefix,
"base_prefix": sys.base_prefix, "version": platform.python_version(),
"architecture": platform.machine() or platform.architecture()[0],
"modules": {name: importlib.util.find_spec(name) is not None for name in required}}))
"""


def discover_attached_comfy_python(
    workspace: Path,
    *,
    environment: dict[str, str] | None = None,
    timeout_seconds: float = _PROBE_TIMEOUT_SECONDS,
) -> ComfyPythonDiscoveryResult:
    """Discover one unambiguous verified interpreter near a Comfy workspace."""

    probes = tuple(
        probe_comfy_python(workspace, candidate, timeout_seconds=timeout_seconds)
        for candidate in attached_comfy_python_candidates(
            workspace, environment=environment
        )
    )
    verified = tuple(probe for probe in probes if probe.binding is not None)
    if not verified:
        return ComfyPythonDiscoveryResult(binding=None, probes=probes)
    best_priority = min(probe.candidate.priority for probe in verified)
    best = tuple(
        probe.binding
        for probe in verified
        if probe.candidate.priority == best_priority and probe.binding is not None
    )
    if len(best) == 1:
        return ComfyPythonDiscoveryResult(binding=best[0], probes=probes)
    return ComfyPythonDiscoveryResult(
        binding=None, probes=probes, ambiguous_bindings=best
    )


def probe_comfy_python(
    workspace: Path,
    candidate: ComfyPythonCandidate | Path,
    *,
    source: ComfyPythonSelectionSource = ComfyPythonSelectionSource.DISCOVERED,
    timeout_seconds: float = _PROBE_TIMEOUT_SECONDS,
) -> ComfyPythonProbeResult:
    """Verify an interpreter using a read-only, timeout-bounded subprocess."""

    normalized = (
        candidate
        if isinstance(candidate, ComfyPythonCandidate)
        else ComfyPythonCandidate(candidate, "user selection", 0)
    )
    executable = normalized.executable.resolve()
    failure = _preflight_failure(workspace, executable)
    if failure is not None:
        return ComfyPythonProbeResult(normalized, None, failure)
    try:
        completed = subprocess.run(
            [str(executable), "-c", _PROBE_SCRIPT],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
    except subprocess.TimeoutExpired:
        return ComfyPythonProbeResult(
            normalized,
            None,
            f"Python probe timed out after {timeout_seconds:g} seconds.",
        )
    except OSError as error:
        return ComfyPythonProbeResult(
            normalized, None, f"Python could not start: {error}"
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        return ComfyPythonProbeResult(
            normalized, None, f"Python probe failed: {detail}"
        )
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        modules = payload["modules"]
        missing = tuple(name for name in _REQUIRED_MODULES if not modules.get(name))
        if missing:
            return ComfyPythonProbeResult(
                normalized,
                None,
                f"Python is missing ComfyUI modules: {', '.join(missing)}.",
            )
        binding = ComfyPythonBinding(
            executable=Path(str(payload["executable"])).resolve(),
            version=str(payload["version"]),
            architecture=str(payload["architecture"]),
            prefix=Path(str(payload["prefix"])).resolve(),
            base_prefix=Path(str(payload["base_prefix"])).resolve(),
            source=source,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return ComfyPythonProbeResult(
            normalized, None, f"Python returned invalid probe data: {error}"
        )
    return ComfyPythonProbeResult(normalized, binding, None)


def resolve_attached_comfy_python(
    workspace: Path, *, explicit_executable: Path | None = None
) -> ComfyPythonBinding:
    """Resolve or verify the interpreter selected for an attached workspace."""

    if not (workspace / "main.py").is_file():
        raise ComfyPythonResolutionError(
            ComfyPythonResolutionFailure.WORKSPACE_INVALID,
            "The selected folder does not contain ComfyUI main.py.",
        )

    if explicit_executable is not None:
        probe = probe_comfy_python(
            workspace,
            explicit_executable,
            source=ComfyPythonSelectionSource.USER_SELECTED,
        )
        if probe.binding is not None:
            return probe.binding
        raise ComfyPythonResolutionError(
            ComfyPythonResolutionFailure.EXPLICIT_SELECTION_INVALID,
            probe.failure or "The selected Python executable is invalid.",
        )
    discovery = discover_attached_comfy_python(workspace)
    if discovery.binding is not None:
        return discovery.binding
    if discovery.requires_user_selection:
        choices = ", ".join(
            str(item.executable) for item in discovery.ambiguous_bindings
        )
        raise ComfyPythonResolutionError(
            ComfyPythonResolutionFailure.AMBIGUOUS,
            "Multiple valid ComfyUI Python environments were found. Choose the "
            f"Python executable to use: {choices}",
            candidates=tuple(item.executable for item in discovery.ambiguous_bindings),
        )
    details = "; ".join(
        f"{probe.candidate.evidence}: {probe.failure}"
        for probe in discovery.probes
        if probe.candidate.executable.exists() and probe.failure
    )
    suffix = f" Probe results: {details}" if details else ""
    raise ComfyPythonResolutionError(
        ComfyPythonResolutionFailure.AUTOMATIC_DISCOVERY_FAILED,
        "Could not find a working Python environment for this ComfyUI folder. "
        "Choose its Python executable with Browse." + suffix,
    )


def managed_comfy_python_binding(workspace: Path) -> ComfyPythonBinding:
    """Verify the canonical interpreter owned by a managed Comfy workspace."""

    probe = probe_comfy_python(
        workspace,
        workspace_python_path(workspace),
        source=ComfyPythonSelectionSource.MANAGED,
    )
    if probe.binding is None:
        raise RuntimeError(probe.failure or "Managed ComfyUI Python is invalid.")
    return probe.binding


def _preflight_failure(workspace: Path, executable: Path) -> str | None:
    """Return a deterministic failure before starting a probe subprocess."""

    if not (workspace / "main.py").is_file():
        return "The selected folder does not contain ComfyUI main.py."
    if not executable.is_file():
        return "Python executable does not exist."
    return None


__all__ = [
    "discover_attached_comfy_python",
    "managed_comfy_python_binding",
    "probe_comfy_python",
    "resolve_attached_comfy_python",
]
