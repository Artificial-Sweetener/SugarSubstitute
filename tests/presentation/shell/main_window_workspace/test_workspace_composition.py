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

"""Characterize the real MainWindow workspace composition boundary."""

from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QProgressBar, QWidget
from cutecanvas import ExecutionRuntime
from pytest import MonkeyPatch
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)

from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.shell import main_window_workspace as workspace
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)


class _OutputCanvas:
    """Provide the Output canvas collaboration required during composition."""

    def __init__(self) -> None:
        """Initialize the captured projection-content registry."""

        self.content_registry: object | None = None

    def create_projection_content_synchronizer(self, registry: object) -> object:
        """Record the registry used to create the Output content synchronizer."""

        self.content_registry = registry
        return object()


class _CanvasHost(QWidget):
    """Provide the real-widget canvas host seam owned outside workspace layout."""

    def __init__(self, create_kwargs: dict[str, object]) -> None:
        """Create the host and its minimal named canvas routes."""

        super().__init__()
        self.create_kwargs = create_kwargs
        self.output_canvas = _OutputCanvas()
        self._canvases = {
            "Input": _InputCanvas(),
            "Output": self.output_canvas,
        }

    def canvas_for(self, canvas_name: str) -> object | None:
        """Return the canvas registered under ``canvas_name``."""

        return self._canvases.get(canvas_name)


class _InputCanvas:
    """Provide the Input document and route collaborators without rendering a canvas."""

    def __init__(self) -> None:
        """Initialize stable input document and route tokens."""

        self.document = object()
        self.route_projector = object()


class _ComfyOutputPanel(QWidget):
    """Provide the shell output-panel boundary without terminal rendering."""

    def __init__(self) -> None:
        """Create an initially hidden output panel."""

        super().__init__()
        self.stream: object | None = None
        self.hide()

    def set_stream(self, stream: object) -> None:
        """Record the terminal stream assigned by the workspace owner."""

        self.stream = stream


class _GenerationProgressStrip(QWidget):
    """Provide the progress-strip rendering boundary for workspace composition."""

    def __init__(self, parent: QWidget) -> None:
        """Create concrete progress bars under the supplied overlay parent."""

        super().__init__(parent)
        self.workflow_bar = QProgressBar(self)
        self.sampler_bar = QProgressBar(self)
        self.progress_visible = False
        self.progress_active = False

    def set_progress_visible(self, visible: bool) -> None:
        """Record requested progress visibility."""

        self.progress_visible = visible

    def set_progress_active(self, active: bool) -> None:
        """Record requested active progress state."""

        self.progress_active = active


class _WorkspaceBodyMaterialSurface(QWidget):
    """Provide the material-surface rendering boundary for layout characterization."""

    def __init__(self, *, parent: QWidget, **_kwargs: object) -> None:
        """Create the surface mounted by the workspace owner."""

        super().__init__(parent)
        self.cube_stack_region_widget: QWidget | None = None

    def set_cube_stack_region_widget(self, widget: QWidget | None) -> None:
        """Record the cube-stack region registered by the workspace owner."""

        self.cube_stack_region_widget = widget


class _WorkspaceCollaborators:
    """Install scoped collaborator seams and retain their observable inputs."""

    def __init__(self) -> None:
        """Initialize collaborator call observations."""

        self.canvas_host: _CanvasHost | None = None
        self.floating_chrome_factory = object()

    def install(self, monkeypatch: MonkeyPatch) -> None:
        """Replace only workspace collaborators that own unrelated behavior."""

        monkeypatch.setattr(workspace, "create_canvas_host", self.create_canvas_host)
        monkeypatch.setattr(
            workspace,
            "create_output_floating_chrome_factory",
            self.create_output_floating_chrome_factory,
        )
        monkeypatch.setattr(workspace, "ComfyOutputPanel", _ComfyOutputPanel)
        monkeypatch.setattr(
            workspace,
            "GenerationProgressStrip",
            _GenerationProgressStrip,
        )
        monkeypatch.setattr(
            workspace,
            "WorkspaceBodyMaterialSurface",
            _WorkspaceBodyMaterialSurface,
        )
        monkeypatch.setattr(workspace, "connect_theme_refresh", _ignore_theme_refresh)

    def create_canvas_host(self, **kwargs: object) -> _CanvasHost:
        """Create a real-widget host and retain the workspace-owned injection set."""

        self.canvas_host = _CanvasHost(kwargs)
        return self.canvas_host

    def create_output_floating_chrome_factory(self) -> object:
        """Return the stable Output chrome collaborator token."""

        return self.floating_chrome_factory


def _ignore_theme_refresh(*_args: object, **_kwargs: object) -> None:
    """Avoid installing global theme callbacks in a composition-only test."""


def test_build_main_window_workspace_composes_deferred_workflow_shell(
    monkeypatch: MonkeyPatch,
) -> None:
    """Build the real shell topology while leaving workflow hydration to its owner."""

    ensure_qt_application()
    collaborators = _WorkspaceCollaborators()
    collaborators.install(monkeypatch)
    window = QMainWindow()
    menu_container = QWidget(window)
    QHBoxLayout(menu_container)
    output_preview_registry = cast(OutputPreviewRegistry, object())

    try:
        widgets = workspace.build_main_window_workspace(
            window,
            canvas_execution_runtime=cast(ExecutionRuntime, object()),
            menu_container=menu_container,
            comfy_output_stream=cast(TerminalOutputStream, object()),
            output_preview_registry=output_preview_registry,
            open_single_external_editor=None,
            open_all_external_editor=None,
        )
        activate_widget_layouts(window, widgets.workspace_body_material_surface)

        assert widgets.workflow_tabbar.count() == 0
        assert window.centralWidget() is not None
        assert window.dockOptions()
        assert collaborators.canvas_host is widgets.canvas_host
        assert collaborators.canvas_host.create_kwargs["output_preview_registry"] is (
            output_preview_registry
        )
        assert (
            collaborators.canvas_host.create_kwargs["output_floating_chrome_factory"]
            is widgets.output_floating_chrome_factory
        )
        assert collaborators.canvas_host.output_canvas.content_registry is (
            widgets.canvas_image_registry
        )
        assert widgets.progress_overlay.isHidden()
        assert widgets.editor_busy_overlay.isHidden()
        assert widgets.comfy_output_panel.isHidden()
        assert widgets.workspace_body_material_surface.cube_stack_region_widget is (
            widgets.cube_stack_container
        )
        assert widgets.workspace_route_container.count() == 2
        assert widgets.workspace_route_container.currentWidget() is (
            widgets.workflow_workspace_page
        )
        assert widgets.workflow_workspace_page.layout().count() == 1
        assert widgets.settings_workspace_layout.count() == 0
        assert widgets.splitter.widget(0) is widgets.editor_output_container
        assert widgets.splitter.widget(1) is widgets.canvas_host_container
        assert widgets.editor_output_splitter.widget(0).layout().itemAt(0).widget() is (
            widgets.cube_stack_container
        )
        assert widgets.editor_output_splitter.widget(0).layout().itemAt(1).widget() is (
            widgets.editor_panel_container
        )
        assert widgets.editor_busy_overlay.parentWidget() is (
            widgets.editor_output_splitter.widget(0)
        )
        assert widgets.editor_output_splitter.widget(1) is widgets.comfy_output_panel
    finally:
        destroy_qt_object(window)
