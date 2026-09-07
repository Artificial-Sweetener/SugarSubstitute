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

"""Define trusted Comfy nodepack manifests required by Substitute."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from substitute.domain.comfy_nodepacks import (
    SUGARCUBES_REQUIRED_VERSION,
    SUBSTITUTE_BACKEND_REQUIRED_VERSION,
    CoreNodepackId,
)

CLI_INSTALL_TIMEOUT_SECONDS = 900
ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS = 120
SUBSTITUTE_BACKEND_FALLBACK_ARCHIVE_URL = (
    "https://github.com/Artificial-Sweetener/Substitute-BackEnd/archive/refs/tags/"
    f"v{SUBSTITUTE_BACKEND_REQUIRED_VERSION}.zip"
)
SUGARCUBES_FALLBACK_ARCHIVE_URL = (
    "https://github.com/Artificial-Sweetener/SugarCubes/archive/refs/tags/"
    f"v{SUGARCUBES_REQUIRED_VERSION}.zip"
)


@dataclass(frozen=True)
class CoreComfyNodepack:
    """Describe one trusted Comfy Registry nodepack Substitute requires."""

    nodepack_id: CoreNodepackId
    registry_id: str
    display_name: str
    publisher: str
    expected_folder: Path
    sentinel_files: tuple[Path, ...]
    required_version: str
    fallback_repository_url: str
    fallback_archive_url: str
    legacy_folders: tuple[Path, ...] = ()
    local_source_environment_variable: str | None = None
    legacy_distribution_name: str | None = None

    @property
    def candidate_folders(self) -> tuple[Path, ...]:
        """Return canonical and persisted legacy installation locations."""

        return (self.expected_folder, *self.legacy_folders)


@dataclass(frozen=True)
class SugarCubesNodepackInstallCandidate:
    """Describe one trusted SugarCubes custom-node repository."""

    source_url: str
    target_folder_name: str


SUGARCUBES_BASE_NODEPACK_INSTALLS: Mapping[
    str, tuple[SugarCubesNodepackInstallCandidate, ...]
] = {
    "comfyui-vectorscope-cc": (
        SugarCubesNodepackInstallCandidate(
            source_url="https://github.com/pamparamm/ComfyUI-vectorscope-cc.git",
            target_folder_name="ComfyUI-vectorscope-cc",
        ),
    ),
    "seedvr2_videoupscaler": (
        SugarCubesNodepackInstallCandidate(
            source_url="https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git",
            target_folder_name="seedvr2_videoupscaler",
        ),
    ),
    "SimpleSyrup": (
        SugarCubesNodepackInstallCandidate(
            source_url="https://github.com/Artificial-Sweetener/SimpleSyrup.git",
            target_folder_name="SimpleSyrup",
        ),
    ),
    "comfyui-prompt-control": (
        SugarCubesNodepackInstallCandidate(
            source_url="https://github.com/asagi4/comfyui-prompt-control.git",
            target_folder_name="comfyui-prompt-control",
        ),
    ),
}
SUGARCUBES_COMPANION_NODEPACKS: Mapping[str, tuple[str, ...]] = {
    "SimpleSyrup": ("comfyui-prompt-control",),
}


CORE_COMFY_NODEPACKS: tuple[CoreComfyNodepack, ...] = (
    CoreComfyNodepack(
        nodepack_id=CoreNodepackId.SUBSTITUTE_BACKEND,
        registry_id="substitute-backend",
        display_name="Substitute BackEnd",
        publisher="artificialsweetener",
        expected_folder=Path("custom_nodes") / "substitute-backend",
        sentinel_files=(
            Path("__init__.py"),
            Path("substitute_backend") / "__init__.py",
        ),
        required_version=SUBSTITUTE_BACKEND_REQUIRED_VERSION,
        fallback_repository_url=(
            "https://github.com/Artificial-Sweetener/Substitute-BackEnd.git"
        ),
        fallback_archive_url=SUBSTITUTE_BACKEND_FALLBACK_ARCHIVE_URL,
        legacy_folders=(Path("custom_nodes") / "Substitute-BackEnd",),
        local_source_environment_variable="SUGARSUBSTITUTE_BACKEND_SOURCE",
        legacy_distribution_name="substitute-backend",
    ),
    CoreComfyNodepack(
        nodepack_id=CoreNodepackId.SUGARCUBES,
        registry_id="SugarCubes",
        display_name="SugarCubes",
        publisher="artificialsweetener",
        expected_folder=Path("custom_nodes") / "SugarCubes",
        sentinel_files=(
            Path("__init__.py"),
            Path("pyproject.toml"),
        ),
        required_version=SUGARCUBES_REQUIRED_VERSION,
        fallback_repository_url=(
            "https://github.com/Artificial-Sweetener/SugarCubes.git"
        ),
        fallback_archive_url=SUGARCUBES_FALLBACK_ARCHIVE_URL,
        local_source_environment_variable="SUGARSUBSTITUTE_SUGARCUBES_SOURCE",
        legacy_distribution_name="SugarCubes",
    ),
)


__all__ = [
    "ARCHIVE_DOWNLOAD_TIMEOUT_SECONDS",
    "CLI_INSTALL_TIMEOUT_SECONDS",
    "CORE_COMFY_NODEPACKS",
    "CoreComfyNodepack",
    "SUGARCUBES_BASE_NODEPACK_INSTALLS",
    "SUGARCUBES_COMPANION_NODEPACKS",
    "SUGARCUBES_FALLBACK_ARCHIVE_URL",
    "SUBSTITUTE_BACKEND_FALLBACK_ARCHIVE_URL",
    "SugarCubesNodepackInstallCandidate",
]
