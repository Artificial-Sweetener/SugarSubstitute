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

"""Define authoritative launcher packaging and runtime platform targets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import platform
from pathlib import Path

from sugarsubstitute_shared.launcher_update.targets import (
    LINUX_X64_BUNDLE,
    MACOS_ARM64_BUNDLE,
    WINDOWS_X64_BUNDLE,
)


class LauncherOperatingSystem(str, Enum):
    """Identify an operating system with an official launcher package."""

    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class LauncherArchitecture(str, Enum):
    """Identify a CPU architecture with an official launcher package."""

    X64 = "x64"
    ARM64 = "arm64"


class InstallerFormat(str, Enum):
    """Identify one public native installer format."""

    WINDOWS_EXE = "exe"
    DMG = "dmg"
    APPIMAGE = "appimage"
    DEB = "deb"


class UnsupportedLauncherPlatformError(RuntimeError):
    """Report a host combination without an official launcher artifact."""


@dataclass(frozen=True, slots=True)
class InstallerSpecification:
    """Own the release filename for one native installer format."""

    format: InstallerFormat
    filename: str


@dataclass(frozen=True, slots=True)
class LauncherTarget:
    """Own platform-specific paths and release names for one launcher target."""

    operating_system: LauncherOperatingSystem
    architecture: LauncherArchitecture
    bundle_root: Path
    executable_relative_path: Path
    support_relative_path: Path
    runtime_python_relative_path: Path
    runtime_gui_python_relative_path: Path
    uv_executable_name: str
    installers: tuple[InstallerSpecification, ...]
    installer_payload_archive_prefix: str
    executable_install_root_parent: int
    icon_asset_name: str

    @property
    def key(self) -> str:
        """Return the stable release-manifest key for this target."""

        return f"{self.operating_system.value}_{self.architecture.value}"

    def install_root_for_executable(self, executable_path: Path) -> Path:
        """Resolve the install root surrounding one target launcher executable."""

        resolved_path = executable_path.expanduser().resolve()
        return resolved_path.parents[self.executable_install_root_parent]

    def installer(self, installer_format: InstallerFormat) -> InstallerSpecification:
        """Return the native installer specification for one supported format."""

        for specification in self.installers:
            if specification.format is installer_format:
                return specification
        raise ValueError(
            f"Target {self.key} does not publish {installer_format.value} installers."
        )

    def installer_key(self, installer_format: InstallerFormat) -> str:
        """Return the schema-two manifest key for one native installer format."""

        self.installer(installer_format)
        return f"{self.key}_{installer_format.value}"

    @property
    def primary_installer(self) -> InstallerSpecification:
        """Return the preferred installer for links that expose one artifact."""

        return self.installers[0]


WINDOWS_X64 = LauncherTarget(
    operating_system=LauncherOperatingSystem.WINDOWS,
    architecture=LauncherArchitecture.X64,
    bundle_root=WINDOWS_X64_BUNDLE.bundle_root,
    executable_relative_path=WINDOWS_X64_BUNDLE.executable_relative_path,
    support_relative_path=WINDOWS_X64_BUNDLE.support_relative_path,
    runtime_python_relative_path=Path(".venv") / "Scripts" / "python.exe",
    runtime_gui_python_relative_path=Path(".venv") / "Scripts" / "pythonw.exe",
    uv_executable_name="uv.exe",
    installers=(
        InstallerSpecification(
            InstallerFormat.WINDOWS_EXE,
            "SugarSubstitute-Installer-Windows-x64.exe",
        ),
    ),
    installer_payload_archive_prefix=(
        "SugarSubstitute-installer-payload-windows-x64-v"
    ),
    executable_install_root_parent=0,
    icon_asset_name="app_icon.ico",
)

MACOS_ARM64 = LauncherTarget(
    operating_system=LauncherOperatingSystem.MACOS,
    architecture=LauncherArchitecture.ARM64,
    bundle_root=MACOS_ARM64_BUNDLE.bundle_root,
    executable_relative_path=MACOS_ARM64_BUNDLE.executable_relative_path,
    support_relative_path=MACOS_ARM64_BUNDLE.support_relative_path,
    runtime_python_relative_path=Path(".venv") / "bin" / "python",
    runtime_gui_python_relative_path=Path(".venv") / "bin" / "python",
    uv_executable_name="uv",
    installers=(
        InstallerSpecification(
            InstallerFormat.DMG,
            "SugarSubstitute-Installer-macOS-Apple-Silicon.dmg",
        ),
    ),
    installer_payload_archive_prefix=(
        "SugarSubstitute-installer-payload-macos-arm64-v"
    ),
    executable_install_root_parent=3,
    icon_asset_name="app_icon_256.png",
)

LINUX_X64 = LauncherTarget(
    operating_system=LauncherOperatingSystem.LINUX,
    architecture=LauncherArchitecture.X64,
    bundle_root=LINUX_X64_BUNDLE.bundle_root,
    executable_relative_path=LINUX_X64_BUNDLE.executable_relative_path,
    support_relative_path=LINUX_X64_BUNDLE.support_relative_path,
    runtime_python_relative_path=Path(".venv") / "bin" / "python",
    runtime_gui_python_relative_path=Path(".venv") / "bin" / "python",
    uv_executable_name="uv",
    installers=(
        InstallerSpecification(
            InstallerFormat.APPIMAGE,
            "SugarSubstitute-Installer-Linux-x86_64.AppImage",
        ),
        InstallerSpecification(
            InstallerFormat.DEB,
            "SugarSubstitute-Installer-Linux-amd64.deb",
        ),
    ),
    installer_payload_archive_prefix="SugarSubstitute-installer-payload-linux-x64-v",
    executable_install_root_parent=0,
    icon_asset_name="app_icon_256.png",
)

SUPPORTED_LAUNCHER_TARGETS: tuple[LauncherTarget, ...] = (
    WINDOWS_X64,
    MACOS_ARM64,
    LINUX_X64,
)


def detect_launcher_target(
    *,
    system: str | None = None,
    machine: str | None = None,
) -> LauncherTarget:
    """Return the official launcher target matching the supplied host."""

    normalized_system = (system or platform.system()).strip().lower()
    normalized_machine = (machine or platform.machine()).strip().lower()
    if normalized_system == "windows" and normalized_machine in {
        "amd64",
        "x86_64",
    }:
        return WINDOWS_X64
    if normalized_system in {"darwin", "macos"} and normalized_machine in {
        "arm64",
        "aarch64",
    }:
        return MACOS_ARM64
    if normalized_system == "linux" and normalized_machine in {
        "amd64",
        "x86_64",
    }:
        return LINUX_X64
    raise UnsupportedLauncherPlatformError(
        "SugarSubstitute launcher packages support Windows x64, macOS Apple "
        "Silicon, and Linux x64. "
        f"Detected system={system or platform.system()!r}, "
        f"machine={machine or platform.machine()!r}."
    )


def launcher_target_for_key(key: str) -> LauncherTarget:
    """Resolve one stable manifest key to its authoritative launcher target."""

    for target in SUPPORTED_LAUNCHER_TARGETS:
        if target.key == key:
            return target
    raise UnsupportedLauncherPlatformError(f"Unsupported launcher target key: {key}")


__all__ = [
    "LauncherArchitecture",
    "InstallerFormat",
    "InstallerSpecification",
    "LauncherOperatingSystem",
    "LauncherTarget",
    "LINUX_X64",
    "MACOS_ARM64",
    "SUPPORTED_LAUNCHER_TARGETS",
    "UnsupportedLauncherPlatformError",
    "WINDOWS_X64",
    "detect_launcher_target",
    "launcher_target_for_key",
]
