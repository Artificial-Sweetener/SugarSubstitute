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

"""Test shell frame titlebar composition and geometry contracts."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QPoint
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication
import pytest
from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButton,
)

from substitute.presentation.shell.chrome_style import (
    APP_ORB_DIAMETER,
    APP_ORB_LEFT_MARGIN,
    APP_ORB_TAB_RESERVED_WIDTH,
    APP_ORB_TOP,
    WORKFLOW_TITLEBAR_HEIGHT,
    WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT,
)
from substitute.presentation.shell.window_frame import (
    APP_ORB_TITLEBAR_SPACER_OBJECT_NAME,
    SubstituteWindowFrame,
    titlebar_menu_content_insert_index,
)
from tests.support.qt.lifecycle import activate_widget_layouts, ensure_qt_application


@pytest.fixture(scope="module", autouse=True)
def frame_composition_qt_application() -> Iterator[QApplication]:
    """Keep one worker-local Qt application alive for frame composition tests."""

    application = ensure_qt_application()
    yield application


def _app() -> QApplication:
    """Return the shared QApplication used by frameless-window contract tests."""

    return ensure_qt_application()


class _WorkflowTabDragOwner:
    """Expose mutable workflow-tab gesture state for titlebar tests."""

    def __init__(self, *, idle: bool) -> None:
        """Store whether the fake workflow-tab gesture is idle."""

        self.idle = idle

    def workflow_tab_gesture_is_idle(self) -> bool:
        """Return whether the fake workflow-tab gesture is idle."""

        return self.idle


def test_shell_frame_inserts_comfy_output_toggle_before_minimize_button() -> None:
    """The shell frame should place the Comfy output toggle in the titlebar cluster."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
    )

    assert frame.menuContainer is not None
    assert frame.comfyOutputToggleButton is not None
    menu_layout = frame.menuContainer.layout()
    assert menu_layout is not None
    assert frame.titleBar.height() == WORKFLOW_TITLEBAR_HEIGHT
    assert menu_layout.contentsMargins().top() == (WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT)
    assert isinstance(frame.comfyOutputToggleButton, TitleBarButton)
    assert frame.comfyOutputToggleButton.isCheckable() is True
    assert frame.comfyOutputToggleButton.toolTip() == "Show Comfy output"
    assert frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) == (
        frame.titleBar.layout().indexOf(frame.titleBar.minBtn) - 1
    )

    frame.set_comfy_output_toggle_checked(True)

    assert frame.comfyOutputToggleButton.isChecked() is True
    assert frame.comfyOutputToggleButton.toolTip() == "Hide Comfy output"

    frame.close()


def test_shell_titlebar_blocks_native_move_during_workflow_tab_gesture() -> None:
    """Active workflow-tab gestures must not become qframeless window drags."""

    _app()
    frame = SubstituteWindowFrame(create_menu_container=True)
    frame.resize(900, 160)
    frame.set_workflow_tab_drag_owner(_WorkflowTabDragOwner(idle=False))

    assert frame.titleBar.canDrag(QPoint(80, 18)) is False

    frame.close()


def test_shell_titlebar_keeps_native_move_when_workflow_tabs_idle() -> None:
    """Idle workflow-tab state should leave qframeless titlebar dragging intact."""

    _app()
    frame = SubstituteWindowFrame(create_menu_container=True)
    frame.resize(900, 160)
    frame.set_workflow_tab_drag_owner(_WorkflowTabDragOwner(idle=True))

    assert frame.titleBar.canDrag(QPoint(80, 18)) is True

    frame.close()


def test_shell_frame_positions_app_orb_as_frame_overlay() -> None:
    """The app orb should overlap titlebar and toolbar as a frame child."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_app_orb_menu=True,
    )
    frame.resize(1200, 800)
    frame.show()
    activate_widget_layouts(frame, frame.titleBar)

    assert frame.appOrbMenuButton is not None
    assert frame.appOrbMenuButton.parentWidget() is frame
    assert frame.appOrbMenuButton.geometry().getRect() == (
        APP_ORB_LEFT_MARGIN,
        APP_ORB_TOP,
        APP_ORB_DIAMETER,
        APP_ORB_DIAMETER,
    )

    frame.resize(1280, 820)
    activate_widget_layouts(frame, frame.titleBar)

    assert frame.appOrbMenuButton.geometry().getRect() == (
        APP_ORB_LEFT_MARGIN,
        APP_ORB_TOP,
        APP_ORB_DIAMETER,
        APP_ORB_DIAMETER,
    )

    frame.close()


def test_shell_frame_titlebar_container_reserves_app_orb_space() -> None:
    """The workflow tabbar insertion index should follow shell-owned spacers."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_app_orb_menu=True,
    )

    assert frame.menuContainer is not None
    menu_layout = frame.menuContainer.layout()
    assert menu_layout is not None
    spacer_item = menu_layout.itemAt(0)
    assert spacer_item is not None
    spacer = spacer_item.widget()
    assert spacer is not None
    assert spacer.objectName() == APP_ORB_TITLEBAR_SPACER_OBJECT_NAME
    assert spacer.minimumWidth() == APP_ORB_TAB_RESERVED_WIDTH
    assert spacer.maximumWidth() == APP_ORB_TAB_RESERVED_WIDTH
    assert titlebar_menu_content_insert_index(frame.menuContainer) == 1

    frame.close()


def test_shell_frame_inserts_generation_cluster_left_of_output_toggle() -> None:
    """The generation cluster should sit directly left of the Comfy output toggle."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
    )

    assert frame.generationActionCluster is not None
    assert frame.comfyOutputToggleButton is not None
    assert frame.generationActionCluster.segment_roles == (
        "stop",
        "play",
        "skip",
        "queue",
    )
    assert frame.generationActionCluster.bottom_corner_radius > 0
    assert frame.generationActionCluster.top_bleed > 0
    assert frame.titleBar.layout().indexOf(frame.generationActionCluster) == (
        frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) - 1
    )
    assert frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) == (
        frame.titleBar.layout().indexOf(frame.titleBar.minBtn) - 1
    )

    frame.close()


def test_shell_frame_inserts_startup_diagnostics_between_generation_and_output() -> (
    None
):
    """Startup diagnostics should sit between generation and console titlebar controls."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
        create_startup_diagnostics_button=True,
    )

    assert frame.generationActionCluster is not None
    assert frame.startupDiagnosticsButton is not None
    assert frame.comfyOutputToggleButton is not None
    layout = frame.titleBar.layout()

    assert layout.indexOf(frame.generationActionCluster) == (
        layout.indexOf(frame.startupDiagnosticsButton) - 1
    )
    assert layout.indexOf(frame.startupDiagnosticsButton) == (
        layout.indexOf(frame.comfyOutputToggleButton) - 1
    )
    assert layout.indexOf(frame.comfyOutputToggleButton) == (
        layout.indexOf(frame.titleBar.minBtn) - 1
    )
    assert frame.startupDiagnosticsButton.is_collapsed() is True

    frame.close()


def test_startup_diagnostics_expansion_settles_left_of_output_before_signal() -> None:
    """Expansion signal should fire after titlebar geometry stops overlapping."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
        create_startup_diagnostics_button=True,
    )
    frame.resize(1440, 900)
    frame.show()
    activate_widget_layouts(frame, frame.titleBar)
    assert frame.startupDiagnosticsButton is not None
    assert frame.comfyOutputToggleButton is not None

    emitted_geometry: list[tuple[int, int]] = []
    expansion = QSignalSpy(frame.startupDiagnosticsButton.expanded)
    frame.startupDiagnosticsButton.expanded.connect(
        lambda: emitted_geometry.append(
            (
                frame.startupDiagnosticsButton.x()
                + frame.startupDiagnosticsButton.width(),
                frame.comfyOutputToggleButton.x(),
            )
        )
    )

    frame.startupDiagnosticsButton.set_collapsed(False)
    assert expansion.wait(2_000), "diagnostics button did not finish expanding"

    assert emitted_geometry
    diagnostics_right, output_left = emitted_geometry[-1]
    assert diagnostics_right <= output_left

    frame.close()


def test_shell_frame_leaves_diagnostics_absent_when_not_requested() -> None:
    """Default shell frame construction should not create a diagnostics titlebar button."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
    )

    assert frame.startupDiagnosticsButton is None
    assert frame.generationActionCluster is not None
    assert frame.comfyOutputToggleButton is not None
    assert frame.titleBar.layout().indexOf(frame.generationActionCluster) == (
        frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) - 1
    )

    frame.close()
