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

"""Verify canonical persistence and drift-free workspace splitter transfer."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QWidget
import pytest

from substitute.presentation.shell.workspace_splitter_controller import (
    WorkspaceSplitterController,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture
def splitter_controller() -> Iterator[tuple[WorkspaceSplitterController, QSplitter]]:
    """Provide the production two-pane hierarchy with exact native cleanup."""

    application = ensure_qt_application()
    splitter = QSplitter(Qt.Orientation.Horizontal)
    details = QWidget()
    canvas = QWidget()
    splitter.addWidget(details)
    splitter.addWidget(canvas)
    splitter.resize(1200, 600)
    splitter.show()
    splitter.ensurePolished()
    splitter.setSizes([700, 500])
    yield (
        WorkspaceSplitterController(
            splitter=splitter,
            details_widget=details,
            canvas_widget=canvas,
        ),
        splitter,
    )
    destroy_qt_object(splitter)
    assert application is ensure_qt_application()


def test_presentation_frames_transfer_from_fixed_origin_without_persisting(
    splitter_controller: tuple[WorkspaceSplitterController, QSplitter],
) -> None:
    """Intermediate animation frames must neither drift nor replace durable sizes."""

    controller, _splitter = splitter_controller
    controller.remember_sizes((700, 500))
    origin = controller.current_sizes()
    assert controller.begin_stack_width_transition(300)

    first = controller.apply_stack_width_frame(200)
    second = controller.apply_stack_width_frame(100)
    repeated = controller.apply_stack_width_frame(100)

    assert first == (origin[0] - 100, origin[1] + 100)
    assert second == (origin[0] - 200, origin[1] + 200)
    assert repeated == second
    assert controller.remembered_sizes == (700, 500)


def test_retarget_uses_live_geometry_as_new_origin(
    splitter_controller: tuple[WorkspaceSplitterController, QSplitter],
) -> None:
    """A reversal should continue from the rendered midpoint without a jump."""

    controller, _splitter = splitter_controller
    origin = controller.current_sizes()
    controller.begin_stack_width_transition(300)
    midpoint = controller.apply_stack_width_frame(150)

    assert controller.begin_stack_width_transition(150)
    assert controller.current_sizes() == midpoint
    assert controller.apply_stack_width_frame(300) == origin


def test_direct_geometry_normalizes_to_preferred_cube_geometry_for_snapshot(
    splitter_controller: tuple[WorkspaceSplitterController, QSplitter],
) -> None:
    """Direct-mode user sizing should restore the same editor width with a stack."""

    controller, splitter = splitter_controller
    splitter.setSizes([400, 800])
    direct_sizes = controller.current_sizes()

    canonical = controller.remember_user_geometry(
        effective_stack_width=0,
        preferred_stack_width=300,
    )

    assert canonical == (direct_sizes[0] + 300, direct_sizes[1] - 300)
    assert (
        controller.sizes_for_snapshot(
            effective_stack_width=0,
            preferred_stack_width=300,
        )
        == canonical
    )
