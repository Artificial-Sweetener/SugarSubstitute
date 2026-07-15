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

"""Load packaged splash pose pixmaps from Qt resources."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QDir, QSize
from PySide6.QtGui import QPixmap

SPLASH_POSE_RESOURCE_PREFIX = ":/substitute/splash/poses"
NUMBERED_POSE_WEIGHT = 1.0
NAMED_POSE_WEIGHT = 0.25
PACKAGED_SPLASH_POSE_SIZE_PX = 386
_RESOURCES_REGISTERED = False


class SplashPoseLibraryError(RuntimeError):
    """Report a packaged splash pose loading failure."""


@dataclass(frozen=True)
class SplashPose:
    """Describe one packaged splash pose pixmap and its selection rarity."""

    name: str
    resource_path: str
    pixmap: QPixmap
    base_weight: float

    @property
    def size(self) -> QSize:
        """Return the loaded pose pixmap size."""

        return self.pixmap.size()


def load_splash_pose_library(
    resource_prefix: str = SPLASH_POSE_RESOURCE_PREFIX,
) -> tuple[SplashPose, ...]:
    """Load all packaged splash poses from the Qt resource prefix."""

    _ensure_resources_registered()
    pose_names = discover_splash_pose_names(resource_prefix)
    poses = tuple(
        _load_pose(resource_prefix=resource_prefix, name=name) for name in pose_names
    )
    if not poses:
        raise SplashPoseLibraryError(
            f"No packaged splash poses were found at {resource_prefix}."
        )
    return poses


def discover_splash_pose_names(
    resource_prefix: str = SPLASH_POSE_RESOURCE_PREFIX,
) -> tuple[str, ...]:
    """Return packaged splash pose names in production display order."""

    _ensure_resources_registered()
    directory = QDir(resource_prefix)
    if not directory.exists():
        raise SplashPoseLibraryError(
            f"Packaged splash pose resource path does not exist: {resource_prefix}"
        )
    names = directory.entryList(["*.png"], QDir.Filter.Files)
    return tuple(sorted(names, key=_pose_sort_key))


def pose_base_weight(name: str) -> float:
    """Return the configured base rarity weight for one pose filename."""

    stem = name.removesuffix(".png")
    if stem.isdigit():
        return NUMBERED_POSE_WEIGHT
    return NAMED_POSE_WEIGHT


def _load_pose(*, resource_prefix: str, name: str) -> SplashPose:
    """Load one packaged pose pixmap and fail clearly if Qt rejects it."""

    resource_path = f"{resource_prefix}/{name}"
    pixmap = QPixmap(resource_path)
    if pixmap.isNull():
        raise SplashPoseLibraryError(
            f"Failed to load packaged splash pose: {resource_path}"
        )
    return SplashPose(
        name=name,
        resource_path=resource_path,
        pixmap=pixmap,
        base_weight=pose_base_weight(name),
    )


def _ensure_resources_registered() -> None:
    """Import the generated Qt resource module exactly when resource access starts."""

    global _RESOURCES_REGISTERED
    if _RESOURCES_REGISTERED:
        return
    from substitute.presentation.resources import splash_poses_rc

    _ = splash_poses_rc
    _RESOURCES_REGISTERED = True


def _pose_sort_key(name: str) -> tuple[int, int | str]:
    """Sort numeric filenames before named filenames without lexical mistakes."""

    stem = name.removesuffix(".png")
    if stem.isdigit():
        return (0, int(stem))
    return (1, stem.casefold())


__all__ = [
    "NAMED_POSE_WEIGHT",
    "NUMBERED_POSE_WEIGHT",
    "PACKAGED_SPLASH_POSE_SIZE_PX",
    "SPLASH_POSE_RESOURCE_PREFIX",
    "SplashPose",
    "SplashPoseLibraryError",
    "discover_splash_pose_names",
    "load_splash_pose_library",
    "pose_base_weight",
]
