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

"""Test application-icon mappings owned by the seed box."""

from __future__ import annotations

from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.seed_box import (
    _FIXED_SEED_ICON,
    _RANDOM_SEED_ICON,
)


def test_seed_box_random_mode_uses_game_die_app_icon() -> None:
    """Resolve random seed mode to the app-managed Game Die icon."""

    assert _RANDOM_SEED_ICON is AppIcon.GAME_DIE_HIGH_CONTRAST


def test_seed_box_fixed_mode_uses_locked_app_icon() -> None:
    """Resolve fixed seed mode to the app-managed Locked icon."""

    assert _FIXED_SEED_ICON is AppIcon.LOCKED_HIGH_CONTRAST
