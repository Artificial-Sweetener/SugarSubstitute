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

"""Own extracted and installed standalone environment filesystem layouts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)


@dataclass(frozen=True, slots=True)
class ExtractedStandaloneLayout:
    """Describe the upstream layout produced by a standalone archive."""

    root: Path

    @property
    def master_environment(self) -> Path:
        """Return the relocatable master Python environment."""

        return self.root / "standalone-env"

    @property
    def comfyui(self) -> Path:
        """Return the bundled ComfyUI repository root."""

        return self.root / "ComfyUI"

    @property
    def manifest(self) -> Path:
        """Return the upstream standalone environment manifest."""

        return self.root / "manifest.json"

    def validate(self, release: StandaloneEnvironmentRelease) -> None:
        """Require archive markers and release identity before promotion."""

        required_files = (self.comfyui / "main.py", self.manifest)
        if not self.master_environment.is_dir() or any(
            not path.is_file() for path in required_files
        ):
            raise StandaloneArtifactError(
                f"Extracted standalone layout is incomplete: {self.root}"
            )
        try:
            payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise StandaloneArtifactError(
                f"Standalone manifest is unreadable: {self.manifest}"
            ) from error
        if not isinstance(payload, dict):
            raise StandaloneArtifactError("Standalone manifest must be a JSON object.")
        manifest = _string_keyed(payload)
        if manifest.get("id") != release.variant.value:
            raise StandaloneArtifactError(
                "Standalone manifest variant does not match the selected release."
            )
        if manifest.get("version") != release.release_tag:
            raise StandaloneArtifactError(
                "Standalone manifest version does not match the selected release."
            )


@dataclass(frozen=True, slots=True)
class ManagedStandaloneLayout:
    """Describe a promoted standalone environment inside a managed workspace."""

    workspace: Path
    variant: StandaloneVariantId

    @property
    def master_environment(self) -> Path:
        """Return the retained relocatable master environment."""

        return self.workspace / ".standalone-env"

    @property
    def virtual_environment(self) -> Path:
        """Return the active ComfyUI virtual environment."""

        return self.workspace / ".venv"

    @property
    def manifest(self) -> Path:
        """Return the persisted standalone release manifest."""

        return self.workspace / ".substitute" / "standalone-environment.json"

    @property
    def master_python(self) -> Path:
        """Return the master interpreter used to build the active environment."""

        if self.variant.value.startswith("win-"):
            return self.master_environment / "python.exe"
        return self.master_environment / "bin" / "python3"

    @property
    def uv_executable(self) -> Path:
        """Return the uv executable bundled with the standalone environment."""

        if self.variant.value.startswith("win-"):
            return self.master_environment / "uv.exe"
        return self.master_environment / "bin" / "uv"

    @property
    def virtual_python(self) -> Path:
        """Return the active ComfyUI Python executable."""

        if self.variant.value.startswith("win-"):
            return self.virtual_environment / "Scripts" / "python.exe"
        return self.virtual_environment / "bin" / "python3"

    def master_site_packages(self) -> Path:
        """Locate the master environment's platform-specific site-packages."""

        return _site_packages(self.master_environment, windows=self._is_windows)

    def virtual_site_packages(self) -> Path:
        """Locate the active virtual environment's site-packages."""

        return _site_packages(self.virtual_environment, windows=self._is_windows)

    def validate_master(self) -> None:
        """Require the promoted runtime tools before creating the active venv."""

        required = (self.workspace / "main.py", self.master_python, self.uv_executable)
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise StandaloneArtifactError(
                f"Promoted standalone environment is incomplete: {missing}"
            )

    @property
    def _is_windows(self) -> bool:
        """Return whether this layout uses Windows Python paths."""

        return self.variant.value.startswith("win-")


def _site_packages(environment: Path, *, windows: bool) -> Path:
    """Locate site-packages without assuming a specific Python minor version."""

    if windows:
        candidate = environment / "Lib" / "site-packages"
        if candidate.is_dir():
            return candidate
    else:
        library_root = environment / "lib"
        if library_root.is_dir():
            for python_root in sorted(library_root.glob("python*")):
                candidate = python_root / "site-packages"
                if candidate.is_dir():
                    return candidate
    raise StandaloneArtifactError(
        f"Could not locate site-packages below {environment}."
    )


def _string_keyed(payload: dict[object, object]) -> dict[str, Any]:
    """Normalize a decoded manifest object to string keys."""

    if any(not isinstance(key, str) for key in payload):
        raise StandaloneArtifactError("Standalone manifest contains a non-string key.")
    return {str(key): value for key, value in payload.items()}
