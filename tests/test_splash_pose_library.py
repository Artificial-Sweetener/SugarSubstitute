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

"""Tests for packaged splash pose resource loading."""

from __future__ import annotations

import os
from typing import cast

import pytest

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "splash pose Qt resource tests load large pixmaps and require non-xdist execution",
        allow_module_level=True,
    )

from PySide6.QtWidgets import QApplication

from substitute.presentation.splash_animation.pose_library import (
    NAMED_POSE_WEIGHT,
    NUMBERED_POSE_WEIGHT,
    PACKAGED_SPLASH_POSE_SIZE_PX,
    SplashPoseLibraryError,
    discover_splash_pose_names,
    load_splash_pose_library,
    pose_base_weight,
)


def _app() -> QApplication:
    """Return the shared QApplication required for QPixmap loading."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_resource_names_load_from_qt_resource_prefix() -> None:
    """Packaged splash poses should be discoverable through Qt resources."""

    names = discover_splash_pose_names()

    assert names[:3] == ("1.png", "2.png", "3.png")
    assert names[-5:] == ("comfy.png", "cubby.png", "liz.png", "ren.png", "witchy.png")


def test_numbered_resource_set_has_no_gaps() -> None:
    """Packaged numbered splash poses should be contiguous from 1 through 24."""

    names = discover_splash_pose_names()
    numbered = tuple(name for name in names if name.removesuffix(".png").isdigit())

    assert numbered == tuple(f"{index}.png" for index in range(1, 25))


def test_pose_weight_policy_distinguishes_numbered_and_named_assets() -> None:
    """Numbered poses should be common and named poses should be rare."""

    assert pose_base_weight("1.png") == pytest.approx(NUMBERED_POSE_WEIGHT)
    assert pose_base_weight("witchy.png") == pytest.approx(NAMED_POSE_WEIGHT)
    assert NAMED_POSE_WEIGHT == pytest.approx(0.25)
    assert NUMBERED_POSE_WEIGHT == pytest.approx(1.0)


def test_pose_library_loads_pixmaps_and_weights() -> None:
    """Packaged splash pose loading should return valid weighted pixmaps."""

    _app()

    poses = load_splash_pose_library()

    assert len(poses) == 29
    assert poses[0].name == "1.png"
    assert poses[0].resource_path == ":/substitute/splash/poses/1.png"
    assert poses[0].base_weight == pytest.approx(NUMBERED_POSE_WEIGHT)
    assert not poses[0].pixmap.isNull()
    assert poses[0].size.width() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[0].size.height() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[-1].name == "witchy.png"
    assert poses[-1].base_weight == pytest.approx(NAMED_POSE_WEIGHT)
    assert not poses[-1].pixmap.isNull()
    assert poses[-1].size.width() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[-1].size.height() == PACKAGED_SPLASH_POSE_SIZE_PX


def test_missing_resource_prefix_raises_library_error() -> None:
    """Missing packaged resource prefixes should fail with a clear error."""

    with pytest.raises(SplashPoseLibraryError, match="does not exist"):
        discover_splash_pose_names(":/substitute/splash/missing")
