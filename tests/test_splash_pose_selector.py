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

"""Tests for recency-aware splash pose selection."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from substitute.presentation.splash_animation.pose_selector import (
    RecencyWeightedPoseSelector,
)


@dataclass(frozen=True)
class DummyPose:
    """Minimal pose record used by selector tests."""

    name: str
    base_weight: float = 1.0


def test_selector_rejects_empty_pose_sequence() -> None:
    """A selector without poses should fail before animation starts."""

    with pytest.raises(ValueError, match="at least one pose"):
        RecencyWeightedPoseSelector(())


def test_selector_rejects_nonpositive_weights() -> None:
    """Invalid rarity weights should fail at construction."""

    with pytest.raises(ValueError, match="weights must be positive"):
        RecencyWeightedPoseSelector((DummyPose("disabled.png", 0.0),))


def test_selector_seeded_draws_are_reproducible() -> None:
    """The same seed should produce the same weighted selection order."""

    poses = (DummyPose("1.png"), DummyPose("2.png"), DummyPose("rare.png", 0.2))
    first = RecencyWeightedPoseSelector(poses, seed=123)
    second = RecencyWeightedPoseSelector(poses, seed=123)

    assert [first.choose_next().name for _ in range(20)] == [
        second.choose_next().name for _ in range(20)
    ]


def test_selector_excludes_current_pose_when_multiple_poses_exist() -> None:
    """The currently visible pose should not be selected back-to-back."""

    poses = (DummyPose("1.png"), DummyPose("2.png"), DummyPose("3.png"))
    selector = RecencyWeightedPoseSelector(poses, seed=12)

    for _ in range(100):
        assert selector.choose_next(current_pose=poses[0]).name != poses[0].name


def test_selector_allows_single_pose_library() -> None:
    """Repeat suppression should not make a one-pose library unusable."""

    pose = DummyPose("1.png")
    selector = RecencyWeightedPoseSelector((pose,), seed=12)

    assert selector.choose_next(current_pose=pose) is pose


def test_named_pose_weight_is_lower_than_numbered_pose_weight() -> None:
    """Rare named poses should carry lower effective weight than numbered poses."""

    numbered = DummyPose("1.png", 1.0)
    named = DummyPose("witchy.png", 0.2)
    selector = RecencyWeightedPoseSelector((numbered, named), seed=12)

    assert selector.effective_weight(named) < selector.effective_weight(numbered)


def test_recently_committed_poses_receive_lower_effective_weights() -> None:
    """The last five committed poses should receive decaying penalties."""

    poses = tuple(DummyPose(f"{index}.png") for index in range(1, 7))
    selector = RecencyWeightedPoseSelector(poses, seed=12)

    selector.commit(poses[0])
    selector.commit(poses[1])
    selector.commit(poses[2])

    assert selector.effective_weight(poses[2]) == pytest.approx(0.10)
    assert selector.effective_weight(poses[1]) == pytest.approx(0.20)
    assert selector.effective_weight(poses[0]) == pytest.approx(0.35)
    assert selector.effective_weight(poses[3]) == pytest.approx(1.0)


def test_pose_older_than_recency_window_returns_to_full_weight() -> None:
    """Committed poses outside the five-turn window should stop being penalized."""

    poses = tuple(DummyPose(f"{index}.png") for index in range(1, 8))
    selector = RecencyWeightedPoseSelector(poses, seed=12)

    for pose in poses[:6]:
        selector.commit(pose)

    assert selector.effective_weight(poses[0]) == pytest.approx(1.0)
    assert selector.effective_weight(poses[5]) == pytest.approx(0.10)
