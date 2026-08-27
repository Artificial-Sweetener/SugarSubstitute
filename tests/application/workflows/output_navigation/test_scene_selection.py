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

"""Verify atomic Output scene navigation selection invariants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)


def test_scene_overview_rejects_partial_concrete_route_state() -> None:
    """Overview selections must not carry a stale scene or source route."""

    with pytest.raises(ValueError, match="Scene overview"):
        OutputSceneNavigationSelection(
            scene_key="scene-a",
            overview=True,
            source_key="source-a",
            set_index=1,
            image_id=None,
        )


def test_concrete_scene_requires_scene_identity() -> None:
    """Concrete scene navigation must identify the scene being entered."""

    with pytest.raises(ValueError, match="requires a scene key"):
        OutputSceneNavigationSelection(
            scene_key=None,
            overview=False,
            source_key="source-a",
            set_index=0,
            image_id=None,
        )


def test_batch_grid_rejects_concrete_image_identity() -> None:
    """Batch-grid selections must not retain one concrete output image."""

    with pytest.raises(ValueError, match="Batch grid"):
        OutputSceneNavigationSelection(
            scene_key="scene-a",
            overview=False,
            source_key="source-a",
            set_index=0,
            image_id=uuid4(),
        )
