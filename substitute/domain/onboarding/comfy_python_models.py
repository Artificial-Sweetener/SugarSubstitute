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

"""Define persisted and transient Comfy Python runtime evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ComfyPythonSelectionSource(str, Enum):
    """Identify how a local Comfy Python executable was selected."""

    MANAGED = "managed"
    DISCOVERED = "discovered"
    USER_SELECTED = "user_selected"


class ComfyPythonResolutionFailure(str, Enum):
    """Classify why an attached Comfy Python binding could not be resolved."""

    WORKSPACE_INVALID = "workspace_invalid"
    AUTOMATIC_DISCOVERY_FAILED = "automatic_discovery_failed"
    AMBIGUOUS = "ambiguous"
    EXPLICIT_SELECTION_INVALID = "explicit_selection_invalid"


class ComfyPythonResolutionError(RuntimeError):
    """Report one typed interpreter-resolution failure to application orchestration."""

    def __init__(
        self,
        reason: ComfyPythonResolutionFailure,
        detail: str,
        *,
        candidates: tuple[Path, ...] = (),
    ) -> None:
        """Preserve the failure reason, technical detail, and possible choices."""

        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.candidates = candidates


@dataclass(frozen=True)
class ComfyPythonBinding:
    """Persist a verified Python interpreter for one local Comfy workspace."""

    executable: Path
    version: str
    architecture: str
    prefix: Path
    base_prefix: Path
    source: ComfyPythonSelectionSource


@dataclass(frozen=True)
class ComfyPythonCandidate:
    """Describe one bounded Python candidate and its discovery evidence."""

    executable: Path
    evidence: str
    priority: int


@dataclass(frozen=True)
class ComfyPythonProbeResult:
    """Capture the result of safely probing one Python executable."""

    candidate: ComfyPythonCandidate
    binding: ComfyPythonBinding | None
    failure: str | None

    @property
    def verified(self) -> bool:
        """Return whether the candidate is a usable Comfy interpreter."""

        return self.binding is not None


@dataclass(frozen=True)
class ComfyPythonDiscoveryResult:
    """Describe automatic selection or the evidence requiring user action."""

    binding: ComfyPythonBinding | None
    probes: tuple[ComfyPythonProbeResult, ...]
    ambiguous_bindings: tuple[ComfyPythonBinding, ...] = ()

    @property
    def requires_user_selection(self) -> bool:
        """Return whether equally credible runtimes need a user choice."""

        return bool(self.ambiguous_bindings)


__all__ = [
    "ComfyPythonBinding",
    "ComfyPythonCandidate",
    "ComfyPythonDiscoveryResult",
    "ComfyPythonProbeResult",
    "ComfyPythonResolutionError",
    "ComfyPythonResolutionFailure",
    "ComfyPythonSelectionSource",
]
