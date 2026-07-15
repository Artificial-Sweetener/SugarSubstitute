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

"""Mount production cube-stack widgets through the real shell layout transition path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from substitute.presentation.shell.cube_stack_mode_transition import (
    CubeStackModeTransition,
)
from substitute.presentation.shell.shell_layout_controller import ShellLayoutController
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
    CubeCloseButtonDisplayMode,
    CubeItem,
    CubeStack,
)


def ensure_qapplication() -> QApplication:
    """Return the process QApplication required by the rendered harness."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


@dataclass(frozen=True, slots=True)
class CubeCardProbe:
    """Capture all state owners that can suppress one cube close button."""

    workflow_id: str
    route_key: str
    shell_compact: bool
    container_width: int
    stack_compact: bool
    stack_transition_active: bool
    stack_width: int
    viewport_width: int
    content_width: int
    card_compact: bool
    card_transition_active: bool
    card_progress: float
    card_width: int
    selected: bool
    hovered: bool
    close_hidden: bool
    close_visible: bool
    close_enabled: bool
    close_visible_region_empty: bool
    close_center_inside_viewport: bool
    close_painted_color_count: int
    close_nontransparent_pixel_count: int
    stack_visible: bool
    card_visible: bool

    @property
    def close_available(self) -> bool:
        """Return whether the rendered close control can receive interaction."""

        return self.close_visible and self.close_enabled


class RealShellCubeStackHarness(QWidget):
    """Drive compact restoration, animation, and workflow swaps with real Qt widgets."""

    def __init__(self, *, start_compact: bool) -> None:
        """Build a visible shell fragment with production stack and transition owners."""

        ensure_qapplication()
        super().__init__()
        self._active_workspace_route = "workflow-a"
        self._cube_stack_compact = False
        self.cube_stacks: dict[str, CubeStack] = {}
        self.autosave_requests = 0

        self.cube_stack_container = QStackedWidget(self)
        self.editor_output_container = QWidget(self)
        self.editor_panel_container = QStackedWidget(self.editor_output_container)
        self.canvas_tabs_container = QWidget(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        editor_layout = QHBoxLayout(self.editor_output_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        editor_layout.addWidget(self.cube_stack_container)
        editor_layout.addWidget(self.editor_panel_container)
        self.splitter.addWidget(self.editor_output_container)
        self.splitter.addWidget(self.canvas_tabs_container)
        self.splitter.setSizes([600, 600])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)
        self.resize(1400, 700)

        self.shell_layout_controller = ShellLayoutController(self)
        self.search_overlay_controller = _SearchOverlayProbe()
        self._cube_stack_mode_transition = CubeStackModeTransition(self)
        self.shell_layout_controller.apply_restored_cube_stack_compact(start_compact)
        self.show()
        self.pump_events()

    def request_session_autosave(self) -> None:
        """Record shell autosave requests made by real layout coordination."""

        self.autosave_requests += 1

    def add_workflow(self, workflow_id: str, aliases: tuple[str, ...]) -> CubeStack:
        """Materialize one production stack under the current restored shell mode."""

        stack = CubeStack(self)
        stack.setMovable(True)
        stack.setTabMaximumWidth(220)
        stack.setCloseButtonDisplayMode(CubeCloseButtonDisplayMode.ON_HOVER)
        self.shell_layout_controller.apply_current_cube_stack_mode_to_stack(stack)
        self.cube_stacks[workflow_id] = stack
        self.cube_stack_container.addWidget(cast(QWidget, stack))
        for alias in aliases:
            stack.addTab(alias, alias)
        if aliases:
            stack.select_cube(aliases[-1], animated=False)
        if self.cube_stack_container.count() == 1:
            self.switch_workflow(workflow_id)
        self.pump_events()
        return stack

    def switch_workflow(self, workflow_id: str) -> None:
        """Swap the real stacked-widget route without mutating cube-card state."""

        self._active_workspace_route = workflow_id
        self.cube_stack_container.setCurrentWidget(
            cast(QWidget, self.cube_stacks[workflow_id])
        )
        self.pump_events()

    def set_compact(self, compact: bool) -> None:
        """Request a mode change through the production shell layout controller."""

        self.shell_layout_controller.set_cube_stack_compact(compact)

    def apply_restored_compact(self, compact: bool) -> None:
        """Apply persisted compact state through the production restore entry point."""

        self.shell_layout_controller.apply_restored_cube_stack_compact(compact)
        self.pump_events()

    def hover_card(self, workflow_id: str, route_key: str) -> None:
        """Move the Qt test cursor over one rendered cube card."""

        stack = self.cube_stacks[workflow_id]
        item = stack.itemMap[route_key]
        QTest.mouseMove(item, item.rect().center())
        self.pump_events()

    def hover_close_location(self, workflow_id: str, route_key: str) -> None:
        """Move the cursor where the close child appears while it is still hidden."""

        stack = self.cube_stacks[workflow_id]
        item = stack.itemMap[route_key]
        QTest.mouseMove(item, item.closeButton.geometry().center())
        self.pump_events()

    def render_expanded_endpoint_without_commit(self, workflow_id: str) -> None:
        """Render the animation endpoint while retaining the prior committed mode."""

        stack = self.cube_stacks[workflow_id]
        stack.beginCompactTransition(False)
        stack.applyCompactTransition(
            stack_width=CUBE_STACK_EXPANDED_WIDTH,
            item_width=CUBE_ITEM_EXPANDED_WIDTH,
            compact_progress=0.0,
        )
        self.cube_stack_container.setFixedWidth(CUBE_STACK_EXPANDED_WIDTH)
        self.pump_events()

    def wait_for_transition(self, timeout_ms: int = 2000) -> None:
        """Pump the real Qt event loop until the production animation completes."""

        timer = QElapsedTimer()
        timer.start()
        while self._cube_stack_mode_transition.is_animating():
            if timer.elapsed() >= timeout_ms:
                raise AssertionError(f"cube stack transition exceeded {timeout_ms} ms")
            QTest.qWait(5)
        self.pump_events()

    def probe(self, workflow_id: str, route_key: str) -> CubeCardProbe:
        """Capture authoritative compact and close-control state for one card."""

        stack = self.cube_stacks[workflow_id]
        item = stack.itemMap[route_key]
        if not isinstance(item, CubeItem):
            raise AssertionError(f"{route_key!r} was not rendered as CubeItem")
        close_image = item.closeButton.grab().toImage()
        painted_colors: set[int] = set()
        nontransparent_pixels = 0
        for y in range(close_image.height()):
            for x in range(close_image.width()):
                color = close_image.pixelColor(x, y)
                painted_colors.add(color.rgba())
                nontransparent_pixels += int(color.alpha() > 0)
        return CubeCardProbe(
            workflow_id=workflow_id,
            route_key=route_key,
            shell_compact=self._cube_stack_compact,
            container_width=self.cube_stack_container.width(),
            stack_compact=stack.isCompact(),
            stack_transition_active=stack._compact_transition_active,
            stack_width=stack.width(),
            viewport_width=stack.viewport().width(),
            content_width=stack.view.width(),
            card_compact=item.isCompact(),
            card_transition_active=item._compact_transition_active,
            card_progress=item.compact_progress(),
            card_width=item.width(),
            selected=item.isSelected,
            hovered=item.isHover,
            close_hidden=item.closeButton.isHidden(),
            close_visible=item.closeButton.isVisible(),
            close_enabled=item.closeButton.isEnabled(),
            close_visible_region_empty=item.closeButton.visibleRegion().isEmpty(),
            close_center_inside_viewport=stack.viewport()
            .rect()
            .contains(
                item.closeButton.mapTo(
                    stack.viewport(), item.closeButton.rect().center()
                )
            ),
            close_painted_color_count=len(painted_colors),
            close_nontransparent_pixel_count=nontransparent_pixels,
            stack_visible=stack.isVisible(),
            card_visible=item.isVisible(),
        )

    def click_close(self, workflow_id: str, route_key: str) -> list[int]:
        """Click the rendered close control and return emitted removal indexes."""

        stack = self.cube_stacks[workflow_id]
        item = stack.itemMap[route_key]
        if not isinstance(item, CubeItem):
            raise AssertionError(f"{route_key!r} was not rendered as CubeItem")
        requests: list[int] = []
        stack.cubeCloseRequested.connect(requests.append)
        QTest.mouseClick(item.closeButton, Qt.MouseButton.LeftButton)
        self.pump_events()
        return requests

    @staticmethod
    def pump_events() -> None:
        """Flush pending layout, visibility, enter/leave, and paint work."""

        app = ensure_qapplication()
        for _ in range(3):
            app.processEvents()
            QTest.qWait(1)


class _SearchOverlayProbe:
    """Accept positioning requests while retaining the real transition path."""

    def __init__(self) -> None:
        """Initialize the positioning counter."""

        self.position_requests = 0

    def position_search_box(self) -> None:
        """Record one search overlay alignment request."""

        self.position_requests += 1


def assert_expanded_close_invariant(probe: CubeCardProbe) -> None:
    """Require a selected expanded card to expose an interactive close control."""

    assert probe.shell_compact is False, probe
    assert probe.container_width == CUBE_STACK_EXPANDED_WIDTH, probe
    assert probe.stack_compact is False, probe
    assert probe.stack_transition_active is False, probe
    assert probe.card_compact is False, probe
    assert probe.card_transition_active is False, probe
    assert probe.card_progress == 0.0, probe
    assert probe.selected is True, probe
    assert probe.close_hidden is False, probe
    assert probe.close_available is True, probe
    assert probe.close_visible_region_empty is False, probe
    assert probe.close_center_inside_viewport is True, probe
    assert probe.close_painted_color_count > 1, probe
    assert probe.close_nontransparent_pixel_count > 0, probe


def assert_compact_close_invariant(probe: CubeCardProbe) -> None:
    """Require a retracted card to suppress close interaction completely."""

    assert probe.shell_compact is True, probe
    assert probe.container_width == CUBE_STACK_COMPACT_WIDTH, probe
    assert probe.stack_compact is True, probe
    assert probe.card_compact is True, probe
    assert probe.card_progress == 1.0, probe
    assert probe.close_hidden is True, probe
    assert probe.close_enabled is False, probe
