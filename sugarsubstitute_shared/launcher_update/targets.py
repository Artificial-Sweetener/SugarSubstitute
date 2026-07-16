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

"""Own platform launcher bundle paths used during safe replacement."""

from __future__ import annotations

from dataclasses import dataclass
import platform
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class LauncherBundleTarget:
    """Describe the immutable paths inside one launcher bundle."""

    key: str
    bundle_root: Path
    executable_relative_path: Path
    support_relative_path: Path
    replacement_roots: tuple[Path, ...]


WINDOWS_X64_BUNDLE = LauncherBundleTarget(
    key="windows_x64",
    bundle_root=Path("."),
    executable_relative_path=Path("SugarSubstitute.exe"),
    support_relative_path=Path("launcher-bin"),
    replacement_roots=(Path("SugarSubstitute.exe"), Path("launcher-bin")),
)
MACOS_ARM64_BUNDLE = LauncherBundleTarget(
    key="macos_arm64",
    bundle_root=Path("SugarSubstitute.app"),
    executable_relative_path=(
        Path("SugarSubstitute.app") / "Contents" / "MacOS" / "SugarSubstitute"
    ),
    support_relative_path=(Path("SugarSubstitute.app") / "Contents" / "Frameworks"),
    replacement_roots=(Path("SugarSubstitute.app"),),
)
LINUX_X64_BUNDLE = LauncherBundleTarget(
    key="linux_x64",
    bundle_root=Path("."),
    executable_relative_path=Path("SugarSubstitute"),
    support_relative_path=Path("launcher-bin"),
    replacement_roots=(Path("SugarSubstitute"), Path("launcher-bin")),
)

_TARGETS = {
    target.key: target
    for target in (WINDOWS_X64_BUNDLE, MACOS_ARM64_BUNDLE, LINUX_X64_BUNDLE)
}


def launcher_bundle_target_for_key(key: str) -> LauncherBundleTarget:
    """Return the supported launcher bundle target with one manifest key."""

    try:
        return _TARGETS[key]
    except KeyError as error:
        raise ValueError(f"Unsupported launcher bundle target: {key}") from error


def detect_launcher_bundle_target() -> LauncherBundleTarget:
    """Return the launcher target matching the current operating system."""

    machine = platform.machine().strip().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return WINDOWS_X64_BUNDLE
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return MACOS_ARM64_BUNDLE
    if sys.platform.startswith("linux") and machine in {"amd64", "x86_64"}:
        return LINUX_X64_BUNDLE
    raise RuntimeError(
        f"Unsupported launcher update platform: {sys.platform}/{platform.machine()}"
    )


__all__ = [
    "LINUX_X64_BUNDLE",
    "MACOS_ARM64_BUNDLE",
    "WINDOWS_X64_BUNDLE",
    "LauncherBundleTarget",
    "detect_launcher_bundle_target",
    "launcher_bundle_target_for_key",
]
