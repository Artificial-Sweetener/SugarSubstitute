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

"""Provide exact-lifetime combo-box fixtures for capability tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QPoint

from substitute.presentation.widgets.combo_box import ComboBox
from tests.presentation.widgets.combo_box.support import (
    DEFAULT_COMBO_ITEMS,
    MountedCombo,
    mount_combo,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture
def combo_box() -> Iterator[ComboBox]:
    """Yield one real combo box and synchronously destroy its Qt owner."""

    ensure_qt_application()
    combo = ComboBox()
    try:
        yield combo
    finally:
        destroy_qt_object(combo)


@pytest.fixture
def combo_mount() -> Iterator[Callable[..., MountedCombo]]:
    """Yield a mounted-combo factory and destroy every created host exactly."""

    ensure_qt_application()
    mounted: list[MountedCombo] = []

    def create(
        *,
        items: tuple[str, ...] = DEFAULT_COMBO_ITEMS,
        host_size: tuple[int, int] = (480, 240),
        host_position: QPoint | None = None,
        combo_position: QPoint | None = None,
    ) -> MountedCombo:
        """Create and retain one mounted combo for fixture-owned cleanup."""

        harness = mount_combo(
            items=items,
            host_size=host_size,
            host_position=host_position,
            combo_position=combo_position,
        )
        mounted.append(harness)
        return harness

    try:
        yield create
    finally:
        for harness in reversed(mounted):
            destroy_qt_object(harness.host)
