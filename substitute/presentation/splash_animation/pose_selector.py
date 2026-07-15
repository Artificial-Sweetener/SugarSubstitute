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

"""Select splash poses with rarity weights and short-term repeat penalties."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
import random
from typing import Generic, Protocol, TypeVar


class WeightedSplashPose(Protocol):
    """Describe the pose fields required by the recency selector."""

    @property
    def name(self) -> str:
        """Return the stable pose name used for recency tracking."""
        ...

    @property
    def base_weight(self) -> float:
        """Return the base rarity weight before recency penalties."""
        ...


PoseT = TypeVar("PoseT", bound=WeightedSplashPose)

_DEFAULT_RECENCY_MULTIPLIERS = (0.10, 0.20, 0.35, 0.55, 0.75)


class RecencyWeightedPoseSelector(Generic[PoseT]):
    """Choose poses by rarity while suppressing recent visual repeats."""

    def __init__(
        self,
        poses: Sequence[PoseT],
        *,
        seed: int | None = None,
        recency_multipliers: Sequence[float] = _DEFAULT_RECENCY_MULTIPLIERS,
    ) -> None:
        """Create a selector with deterministic random state when seeded."""

        if not poses:
            raise ValueError("RecencyWeightedPoseSelector requires at least one pose.")
        invalid_names = [pose.name for pose in poses if pose.base_weight <= 0]
        if invalid_names:
            joined_names = ", ".join(invalid_names)
            raise ValueError(f"Splash pose weights must be positive: {joined_names}")

        self._poses = tuple(poses)
        self._random = random.Random(seed)
        self._seed = seed
        self._recency_multipliers = tuple(
            max(0.0, min(1.0, multiplier)) for multiplier in recency_multipliers
        )
        self._recent_pose_names: deque[str] = deque(
            maxlen=len(self._recency_multipliers)
        )

    @property
    def seed(self) -> int | None:
        """Return the deterministic random seed, if one was provided."""

        return self._seed

    @property
    def recent_pose_names(self) -> tuple[str, ...]:
        """Return recently committed pose names from newest to oldest."""

        return tuple(reversed(self._recent_pose_names))

    def choose_next(self, *, current_pose: PoseT | None = None) -> PoseT:
        """Return the next weighted pose after rarity and recency penalties."""

        candidates = self._candidate_poses(current_pose=current_pose)
        weights = [self.effective_weight(pose) for pose in candidates]
        if all(weight <= 0 for weight in weights):
            weights = [pose.base_weight for pose in candidates]
        return self._random.choices(candidates, weights=weights, k=1)[0]

    def commit(self, pose: PoseT) -> None:
        """Record one pose as visible so later choices can penalize repeats."""

        self._recent_pose_names.append(pose.name)

    def effective_weight(self, pose: PoseT) -> float:
        """Return the current selection weight for one pose."""

        return pose.base_weight * self._recency_multiplier(pose.name)

    def _candidate_poses(self, *, current_pose: PoseT | None) -> tuple[PoseT, ...]:
        """Return selectable poses for one draw, excluding current when possible."""

        if current_pose is None or len(self._poses) == 1:
            return self._poses
        filtered = tuple(pose for pose in self._poses if pose.name != current_pose.name)
        return filtered or self._poses

    def _recency_multiplier(self, pose_name: str) -> float:
        """Return the configured multiplier for a recently committed pose."""

        for index, recent_name in enumerate(reversed(self._recent_pose_names)):
            if pose_name == recent_name:
                return self._recency_multipliers[index]
        return 1.0


__all__ = ["RecencyWeightedPoseSelector", "WeightedSplashPose"]
