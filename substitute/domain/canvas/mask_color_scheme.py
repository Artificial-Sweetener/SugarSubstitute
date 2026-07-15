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

"""Choose deterministic mask color hues for related mask sets."""

from __future__ import annotations


def mask_color_hue(base_hue: int, index: int, total_masks: int) -> int:
    """Return the hue for one mask within a related mask set.

    The first mask keeps the application accent hue. Additional masks use
    familiar color-theory spacing so linked masks remain visually distinct
    without requiring Qt or theme dependencies in the policy.
    """

    normalized_hue = base_hue % 360
    if index <= 0:
        return normalized_hue

    if total_masks == 2:
        return (normalized_hue + 180) % 360

    if total_masks == 3:
        complementary_hue = (normalized_hue + 180) % 360
        if index == 1:
            return (complementary_hue - 30) % 360
        return (complementary_hue + 30) % 360

    if total_masks == 4:
        return (normalized_hue + (index * 90)) % 360

    if total_masks >= 5:
        angle_step = 360 / total_masks
        return int((normalized_hue + (index * angle_step)) % 360)

    return normalized_hue
