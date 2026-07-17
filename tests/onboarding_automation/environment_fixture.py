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

"""Provide deterministic Comfy environment boundaries for onboarding automation."""

from __future__ import annotations

from pathlib import Path

from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonSelectionSource,
    LocalComfyProcess,
    LocalComfyTerminationResult,
)


class QuiescentProcessGateway:
    """Keep general onboarding scenarios independent of workstation processes."""

    def scan(self) -> tuple[LocalComfyProcess, ...]:
        """Report no process blocker in deterministic UI scenarios."""

        return ()

    def terminate(
        self,
        processes: tuple[LocalComfyProcess, ...],
    ) -> LocalComfyTerminationResult:
        """Reject an impossible termination request in the quiescent fixture."""

        requested = tuple(item.pid for item in processes)
        return LocalComfyTerminationResult(requested, (), requested, ())


class StaticPythonGateway:
    """Return one predefined verified binding for synthetic attached scenarios."""

    def __init__(self, binding: ComfyPythonBinding) -> None:
        """Store the binding exposed through discovery and browse validation."""

        self._binding = binding

    def discover(self, workspace: Path) -> ComfyPythonDiscoveryResult:
        """Return the configured binding for its selected workspace."""

        _ = workspace
        return ComfyPythonDiscoveryResult(binding=self._binding, probes=())

    def probe(
        self,
        workspace: Path,
        executable: Path,
        *,
        source: ComfyPythonSelectionSource,
    ) -> ComfyPythonProbeResult:
        """Return equivalent evidence with the requested recovery source."""

        _ = workspace
        binding = ComfyPythonBinding(
            executable=executable,
            version=self._binding.version,
            architecture=self._binding.architecture,
            prefix=executable.parent.parent,
            base_prefix=executable.parent.parent,
            source=source,
        )
        return ComfyPythonProbeResult(
            candidate=ComfyPythonCandidate(executable, "automation fixture", 0),
            binding=binding,
            failure=None,
        )


def synthetic_python_binding(executable: Path) -> ComfyPythonBinding:
    """Build deterministic verified evidence for a synthetic executable path."""

    return ComfyPythonBinding(
        executable=executable,
        version="3.13",
        architecture="AMD64",
        prefix=executable.parent.parent,
        base_prefix=executable.parent.parent,
        source=ComfyPythonSelectionSource.DISCOVERED,
    )


__all__ = [
    "QuiescentProcessGateway",
    "StaticPythonGateway",
    "synthetic_python_binding",
]
