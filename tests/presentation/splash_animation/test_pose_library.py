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

import pytest

from substitute.presentation.splash_animation.pose_library import (
    GUEST_POSE_WEIGHT,
    NUMBERED_POSE_WEIGHT,
    PACKAGED_SPLASH_POSE_SIZE_PX,
    RARE_GUEST_POSE_WEIGHT,
    SplashPoseLibraryError,
    discover_splash_pose_names,
    load_splash_pose_library,
    pose_base_weight,
)


def test_resource_names_load_from_qt_resource_prefix() -> None:
    """Packaged splash poses should be discoverable through Qt resources."""

    names = discover_splash_pose_names()

    assert names[:3] == ("1.png", "2.png", "3.png")
    assert names[-12:] == (
        "cass.png",
        "comfy.png",
        "comfy2.png",
        "cubby.png",
        "diffusion.png",
        "liz.png",
        "lvgf.png",
        "married.png",
        "pixelandlibrary.png",
        "ren.png",
        "syl.png",
        "witchy.png",
    )


def test_numbered_resource_set_has_no_gaps() -> None:
    """Packaged numbered splash poses should be contiguous from 1 through 28."""

    names = discover_splash_pose_names()
    numbered = tuple(name for name in names if name.removesuffix(".png").isdigit())

    assert numbered == tuple(f"{index}.png" for index in range(1, 29))


def test_pose_weight_policy_distinguishes_common_and_guest_assets() -> None:
    """Numbered, guest, and rare-guest poses should use their own weights."""

    assert pose_base_weight("1.png") == pytest.approx(NUMBERED_POSE_WEIGHT)
    assert pose_base_weight("witchy.png") == pytest.approx(GUEST_POSE_WEIGHT)
    assert pose_base_weight("married.png") == pytest.approx(RARE_GUEST_POSE_WEIGHT)
    assert GUEST_POSE_WEIGHT == pytest.approx(0.25)
    assert RARE_GUEST_POSE_WEIGHT == pytest.approx(GUEST_POSE_WEIGHT / 2)
    assert NUMBERED_POSE_WEIGHT == pytest.approx(1.0)


def test_new_guest_poses_use_requested_rarities() -> None:
    """New guest poses should share one weight except for the married couple."""

    guest_names = (
        "comfy2.png",
        "diffusion.png",
        "lvgf.png",
        "pixelandlibrary.png",
        "syl.png",
    )

    assert all(
        pose_base_weight(name) == pytest.approx(GUEST_POSE_WEIGHT)
        for name in guest_names
    )
    assert pose_base_weight("married.png") == pytest.approx(GUEST_POSE_WEIGHT / 2)


def test_pose_library_loads_pixmaps_and_weights() -> None:
    """Packaged splash pose loading should return valid weighted pixmaps."""

    poses = load_splash_pose_library()

    assert len(poses) == 40
    assert poses[0].name == "1.png"
    assert poses[0].resource_path == ":/substitute/splash/poses/1.png"
    assert poses[0].base_weight == pytest.approx(NUMBERED_POSE_WEIGHT)
    assert not poses[0].pixmap.isNull()
    assert poses[0].size.width() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[0].size.height() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[-1].name == "witchy.png"
    assert poses[-1].base_weight == pytest.approx(GUEST_POSE_WEIGHT)
    assert not poses[-1].pixmap.isNull()
    assert poses[-1].size.width() == PACKAGED_SPLASH_POSE_SIZE_PX
    assert poses[-1].size.height() == PACKAGED_SPLASH_POSE_SIZE_PX


def test_missing_resource_prefix_raises_library_error() -> None:
    """Missing packaged resource prefixes should fail with a clear error."""

    with pytest.raises(SplashPoseLibraryError, match="does not exist"):
        discover_splash_pose_names(":/substitute/splash/missing")
