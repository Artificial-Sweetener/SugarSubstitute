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

"""Verify three-mode cube-stack presentation through production Qt widgets."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from substitute.domain.workflow import WorkflowDocumentKind
from substitute.presentation.shell.cube_stack_presentation_controller import (
    CubeStackPresentationController,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.app_orb_action_cluster import (
    AppOrbCubeStackButton,
)
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPreference,
    CubeStackPresentationMode,
)
from substitute.presentation.shell.workspace_splitter_controller import (
    WorkspaceSplitterController,
)
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.workflows.cube_stack_view import CubeStack


def _application() -> QApplication:
    """Return the QApplication required by production Qt widgets."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


class _MaterialSurface:
    """Record production material port mutations."""

    def __init__(self) -> None:
        """Initialize material histories."""

        self.regions: list[QStackedWidget | None] = []
        self.opacities: list[float] = []

    def set_cube_stack_region_widget(self, widget: QStackedWidget | None) -> None:
        """Record the current material exclusion widget."""

        self.regions.append(widget)

    def set_cube_stack_wash_opacity(self, opacity: float) -> None:
        """Record one material wash opacity."""

        self.opacities.append(opacity)


class _EditorSurface:
    """Record editor-gutter progress applied by presentation frames."""

    def __init__(self) -> None:
        """Initialize an empty progress history."""

        self.progresses: list[float] = []

    def set_cube_stack_unavailable_progress(self, progress: float) -> None:
        """Record one direct-Comfy gutter progress value."""

        self.progresses.append(progress)


def _controller() -> tuple[
    QWidget,
    CubeStackPresentationController,
    QStackedWidget,
    CubeStack,
    AppOrbCubeStackButton,
    QSplitter,
    _MaterialSurface,
    _EditorSurface,
]:
    """Build the production workspace hierarchy around a real CubeStack."""

    app = _application()
    root = QWidget()
    splitter = QSplitter(Qt.Orientation.Horizontal, root)
    details = QWidget(splitter)
    canvas = QWidget(splitter)
    details_layout = QHBoxLayout(details)
    details_layout.setContentsMargins(0, 0, 0, 0)
    container = QStackedWidget(details)
    editor = QWidget(details)
    details_layout.addWidget(container)
    details_layout.addWidget(editor, 1)
    stack = CubeStack(container)
    container.addWidget(cast(QWidget, stack))
    splitter.addWidget(details)
    splitter.addWidget(canvas)
    root_layout = QHBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.addWidget(splitter)
    root.resize(1400, 700)
    root.show()
    splitter.setSizes([800, 600])
    app.processEvents()

    button = AppOrbCubeStackButton(root)
    material = _MaterialSurface()
    editor_surface = _EditorSurface()
    stacks: tuple[CubeStack, ...] = (stack,)

    def stack_provider() -> Iterable[CubeStack]:
        """Return the live workflow stack collection."""

        return stacks

    splitter_controller = WorkspaceSplitterController(
        splitter=splitter,
        details_widget=details,
        canvas_widget=canvas,
    )
    controller = CubeStackPresentationController(
        container=container,
        stacks=stack_provider,
        mode_button=button,
        material_surface=material,
        active_editor_surface=lambda: editor_surface,
        splitter_controller=splitter_controller,
        position_search_box=lambda: None,
        request_autosave=lambda: None,
        duration_resolver=lambda _duration: 0,
        parent=root,
    )
    app.processEvents()
    return (
        root,
        controller,
        container,
        stack,
        button,
        splitter,
        material,
        editor_surface,
    )


def test_direct_document_hides_stack_disables_button_and_transfers_width() -> None:
    """Unavailable mode should surrender stack width to canvas at one exact endpoint."""

    (
        _root,
        controller,
        container,
        _stack,
        button,
        splitter,
        material,
        editor_surface,
    ) = _controller()
    cube_sizes = tuple(splitter.sizes())

    controller.activate_document_kind(
        WorkflowDocumentKind.DIRECT_COMFY,
        animated=False,
    )
    _application().processEvents()
    direct_sizes = tuple(splitter.sizes())

    assert controller.mode is CubeStackPresentationMode.UNAVAILABLE
    assert controller.current_frame().container_width == 0
    assert container.isHidden()
    assert not button.isEnabled()
    assert button._icon is AppIcon.PANEL_LEFT_20_FILLED
    assert button._icon_color().alpha() == 92
    assert button.accessibleName() == "Cube stack unavailable for Comfy workflows"
    assert direct_sizes[0] == cube_sizes[0] - CUBE_STACK_EXPANDED_WIDTH
    assert direct_sizes[1] == cube_sizes[1] + CUBE_STACK_EXPANDED_WIDTH
    assert material.regions[-1] is None
    assert editor_surface.progresses[-1] == 1.0


def test_cube_document_restores_preference_and_inverse_splitter_transfer() -> None:
    """Returning to a cube document should exactly reverse unavailable geometry."""

    (
        _root,
        controller,
        container,
        stack,
        button,
        splitter,
        _material,
        editor_surface,
    ) = _controller()
    controller.restore_preference(True)
    cube_sizes = tuple(splitter.sizes())
    controller.activate_document_kind(
        WorkflowDocumentKind.DIRECT_COMFY,
        animated=False,
    )

    controller.activate_document_kind(
        WorkflowDocumentKind.CUBE_STACK,
        animated=False,
    )
    _application().processEvents()

    assert controller.preference is CubeStackPreference.COMPACT
    assert controller.mode is CubeStackPresentationMode.COMPACT
    assert controller.current_frame().container_width == CUBE_STACK_COMPACT_WIDTH
    assert tuple(splitter.sizes()) == cube_sizes
    assert container.isVisible()
    assert stack.isCompact()
    assert button.isEnabled()
    assert button.isChecked()
    assert editor_surface.progresses[-1] == 0.0


def test_expansion_lease_cannot_override_direct_document_availability() -> None:
    """Rename-style expansion leases must remain subordinate to document kind."""

    (
        _root,
        controller,
        container,
        _stack,
        button,
        _splitter,
        _material,
        _editor_surface,
    ) = _controller()
    controller.restore_preference(True)
    controller.activate_document_kind(
        WorkflowDocumentKind.DIRECT_COMFY,
        animated=False,
    )

    lease = controller.acquire_expansion()

    assert lease.active
    assert controller.mode is CubeStackPresentationMode.UNAVAILABLE
    assert container.isHidden()
    assert not button.isEnabled()
    lease.release()
    assert not lease.active
