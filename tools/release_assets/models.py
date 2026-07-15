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

"""Define immutable release-assembly inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from launcher.sugarsubstitute_launcher.platforms import InstallerFormat, LauncherTarget


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """Describe one file resolved through the release manifest."""

    filename: str
    url: str
    sha256: str
    size_bytes: int

    def to_json(self) -> dict[str, str | int]:
        """Return the JSON-safe representation for this release asset."""

        return {
            "filename": self.filename,
            "url": self.url,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class NativeInstallerInput:
    """Bind one native installer format to its built artifact."""

    format: InstallerFormat
    source_path: Path


@dataclass(frozen=True, slots=True)
class PlatformReleaseInput:
    """Describe built launcher and native installer artifacts for one target."""

    target: LauncherTarget
    launcher_source: Path
    installers: tuple[NativeInstallerInput, ...]

    def validate(self) -> None:
        """Require exactly the native formats promised by the target policy."""

        expected = {specification.format for specification in self.target.installers}
        actual = {installer.format for installer in self.installers}
        if len(actual) != len(self.installers):
            raise ValueError(f"Duplicate installer formats for {self.target.key}.")
        if actual != expected:
            missing = sorted(value.value for value in expected - actual)
            unexpected = sorted(value.value for value in actual - expected)
            raise ValueError(
                f"Installer inputs for {self.target.key} do not match platform policy; "
                f"missing={missing}, unexpected={unexpected}."
            )


@dataclass(frozen=True, slots=True)
class LocalReleaseBuildResult:
    """Describe files produced for one local release-channel rebuild."""

    app_zip_path: Path
    manifest_path: Path
    checksums_path: Path
    app_asset: ReleaseAsset
    launcher_assets: Mapping[str, ReleaseAsset]
    installer_assets: Mapping[str, ReleaseAsset]
