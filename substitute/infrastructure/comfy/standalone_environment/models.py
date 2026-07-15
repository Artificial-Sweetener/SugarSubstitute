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

"""Define immutable standalone-environment catalog and artifact models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StandaloneVariantId(str, Enum):
    """Identify a platform and accelerator bundle published by Comfy Desktop."""

    WINDOWS_NVIDIA = "win-nvidia"
    WINDOWS_AMD = "win-amd"
    WINDOWS_INTEL_XPU = "win-intel-xpu"
    WINDOWS_CPU = "win-cpu"
    LINUX_NVIDIA = "linux-nvidia"
    LINUX_AMD = "linux-amd"
    LINUX_INTEL_XPU = "linux-intel-xpu"
    MACOS_MPS = "mac-mps"


class StandaloneArchiveKind(str, Enum):
    """Identify extraction behavior for a standalone bundle."""

    SEVEN_ZIP = "7z"
    TAR_GZIP = "tar.gz"


@dataclass(frozen=True, slots=True)
class StandaloneArtifact:
    """Describe one checksum-addressed part of a standalone archive."""

    filename: str
    url: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class StandaloneEnvironmentRelease:
    """Describe one verified relocatable Comfy environment release."""

    variant: StandaloneVariantId
    release_tag: str
    comfyui_version: str
    comfyui_commit: str
    python_version: str
    torch_version: str
    archive_kind: StandaloneArchiveKind
    artifacts: tuple[StandaloneArtifact, ...]

    @property
    def total_size_bytes(self) -> int:
        """Return the complete download size across archive parts."""

        return sum(artifact.size_bytes for artifact in self.artifacts)


class StandaloneCatalogError(RuntimeError):
    """Report malformed or unverifiable standalone release metadata."""


class StandaloneArtifactError(RuntimeError):
    """Report a standalone download, checksum, or extraction failure."""
