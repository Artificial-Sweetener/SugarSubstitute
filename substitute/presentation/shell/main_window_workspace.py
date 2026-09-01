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

"""Build the MainWindow workspace scaffold and long-lived shell containers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from cutecanvas import ExecutionRuntime
from qfluentwidgets import ProgressBar  # type: ignore[import-untyped]

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


from substitute.application.workflows import (
    InputCanvasStateService,
    OutputCanvasProjectionCoordinator,
    WorkflowCanvasProjectionCoordinator,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_generated_result_service import (
    OutputGeneratedResultService,
)
from substitute.application.workflows.output_canvas_timing_service import (
    OutputCanvasTimingService,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from substitute.presentation.canvas import (
    create_canvas_host,
    create_output_floating_chrome_factory,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.shell.comfy_output_panel import ComfyOutputPanel
from substitute.presentation.shell.chrome_style import (
    CUBE_STACK_TOP_INSET,
    connect_theme_refresh,
    splitter_handle_rgba,
)
from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
)
from substitute.presentation.shell.editor_busy_overlay import EditorBusyOverlay
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.window_frame import (
    titlebar_menu_content_insert_index,
)
from substitute.presentation.shell.workspace_body_material_surface import (
    WorkspaceBodyMaterialSurface,
)
from substitute.presentation.workflows.cube_stack_view import CUBE_STACK_EXPANDED_WIDTH
from substitute.presentation.workflows.workflow_tabs_view import (
    TabBar,
    TabCloseButtonDisplayMode,
)
from substitute.shared.startup_trace import trace_mark, trace_span

OutputSingleExternalEditor = Callable[[object, OutputImageMeta], bool]
OutputAllExternalEditor = Callable[[list[tuple[object, OutputImageMeta]]], bool]
OutputAssetReveal = Callable[[OutputImageMeta], bool]


@dataclass(frozen=True)
class MainWindowWorkspaceWidgets:
    """Bundle the workspace containers and shell widgets built for MainWindow."""

    workflow_tab_service: WorkflowTabService
    workflow_session_service: WorkflowSessionService[Any]
    workflow_tabbar: TabBar
    workspace_body_material_surface: WorkspaceBodyMaterialSurface
    workspace_route_container: QStackedWidget
    workflow_workspace_page: QWidget
    settings_workspace_page: QWidget
    settings_workspace_layout: QHBoxLayout
    cube_stack_container: QStackedWidget
    editor_output_container: QWidget
    editor_output_splitter: QSplitter
    editor_panel_container: QStackedWidget
    editor_busy_overlay: EditorBusyOverlay
    comfy_output_panel: ComfyOutputPanel
    canvas_host: Any
    input_canvas_state_service: InputCanvasStateService
    output_canvas_state_service: OutputCanvasStateService
    output_canvas_focus_service: OutputCanvasFocusService
    output_navigation_session_service: OutputNavigationSessionService
    output_generated_result_service: OutputGeneratedResultService
    output_canvas_timing_service: OutputCanvasTimingService
    output_canvas_projection_coordinator: OutputCanvasProjectionCoordinator
    workflow_canvas_projection_coordinator: WorkflowCanvasProjectionCoordinator
    canvas_image_registry: CanvasImageRegistry
    output_floating_chrome_factory: Any
    canvas_host_container: QWidget
    side_panel_host: "WorkspaceSidePanelHost"
    splitter: QSplitter
    progress_overlay: QWidget
    workflow_overlay_bar: ProgressBar
    sampler_overlay_bar: ProgressBar


class WorkspaceSidePanelHost(QWidget):
    """Host optional right-side workspace panels behind stable layout APIs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an initially hidden side-panel host."""

        super().__init__(parent)
        self._panel_width = 360
        self.setFixedWidth(self._panel_width)
        self.hide()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def set_queue_panel(self, panel: QWidget) -> None:
        """Replace hosted panel content with the generation queue panel."""

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._layout.addWidget(panel)

    def set_queue_panel_visible(self, visible: bool) -> None:
        """Show or hide the queue side panel host."""

        self.begin_width_transition(target_visible=visible)
        self.finish_width_transition(visible=visible)

    def begin_width_transition(self, *, target_visible: bool) -> None:
        """Prepare host visibility before an animated width transition."""

        _ = target_visible
        self.show()

    def apply_width_transition(self, width: int) -> None:
        """Apply one rendered side-panel width without changing durable width."""

        self.setFixedWidth(max(0, width))

    def finish_width_transition(self, *, visible: bool) -> None:
        """Commit final host visibility after an animated width transition."""

        if visible:
            self.show()
            self.setFixedWidth(self._panel_width)
            return
        self.setFixedWidth(0)
        self.hide()

    def is_queue_panel_visible(self) -> bool:
        """Return whether the queue side panel host is visible."""

        return self.isVisible()

    def set_panel_width(self, width: int) -> None:
        """Set the fixed side-panel width."""

        self._panel_width = max(240, width)
        self.setFixedWidth(self._panel_width)

    def panel_width(self) -> int:
        """Return the configured side-panel width."""

        return self._panel_width

    def rendered_width(self) -> int:
        """Return the current live side-panel host width."""

        return self.width()


def _build_workflow_tabbar(
    window: object,
    menu_container: QWidget,
    backdrop_mode: ShellBackdropMode | None,
) -> tuple[
    WorkflowTabService,
    WorkflowSessionService[Any],
    TabBar,
]:
    """Build the workflow tab row and attach it to the custom titlebar container."""

    workflow_tab_service = WorkflowTabService()
    workflow_session_service: WorkflowSessionService[Any] = WorkflowSessionService()
    workflow_tabbar = TabBar(window)
    set_backdrop_mode = getattr(workflow_tabbar, "set_backdrop_mode", None)
    if callable(set_backdrop_mode):
        set_backdrop_mode(backdrop_mode)
    workflow_tabbar.setMovable(True)
    workflow_tabbar.setTabMaximumWidth(180)
    workflow_tabbar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)
    workflow_tabbar.setMinimumHeight(10)

    menu_layout = menu_container.layout()
    if menu_layout is None:
        raise RuntimeError("Menu container must expose a layout for workflow tabs.")
    typed_menu_layout = cast(QHBoxLayout, menu_layout)
    insert_index = titlebar_menu_content_insert_index(menu_container)
    typed_menu_layout.insertWidget(insert_index, cast(QWidget, workflow_tabbar))
    typed_menu_layout.setStretch(insert_index, 8)
    if insert_index > 0:
        typed_menu_layout.setStretch(insert_index - 1, 0)
    if typed_menu_layout.count() > insert_index + 1:
        typed_menu_layout.setStretch(insert_index + 1, 2)
    return workflow_tab_service, workflow_session_service, workflow_tabbar


def _build_canvas_scaffold(
    window: object,
    *,
    canvas_execution_runtime: ExecutionRuntime,
    output_preview_registry: OutputPreviewRegistry,
    open_single_external_editor: OutputSingleExternalEditor | None,
    open_all_external_editor: OutputAllExternalEditor | None,
    reveal_output_asset: OutputAssetReveal | None = None,
) -> tuple[
    Any,
    InputCanvasStateService,
    OutputCanvasStateService,
    OutputCanvasFocusService,
    OutputNavigationSessionService,
    OutputGeneratedResultService,
    OutputCanvasTimingService,
    OutputCanvasProjectionCoordinator,
    WorkflowCanvasProjectionCoordinator,
    CanvasImageRegistry,
    Any,
    QWidget,
]:
    """Build the canvas host, state owners, and its container widget."""

    canvas_session_boundary = create_canvas_session_boundary()
    canvas_image_registry = CanvasImageRegistry()
    output_floating_chrome_factory = create_output_floating_chrome_factory()
    with trace_span("mainwindow.build_workspace.canvas.create_host"):
        canvas_host = create_canvas_host(
            execution_runtime=canvas_execution_runtime,
            output_preview_registry=output_preview_registry,
            open_single_external_editor=open_single_external_editor,
            open_all_external_editor=open_all_external_editor,
            reveal_output_asset=reveal_output_asset,
            final_output_payload_lookup=canvas_image_registry.payload_for,
            final_output_metadata_lookup=canvas_image_registry.metadata_for,
            output_floating_chrome_factory=output_floating_chrome_factory,
            route_session_boundary=canvas_session_boundary,
        )
    with trace_span("mainwindow.build_workspace.canvas.validate_host"):
        output_canvas = cast(Any, canvas_host.canvas_for("Output"))
        input_canvas = cast(Any, canvas_host.canvas_for("Input"))
        if input_canvas is None or output_canvas is None:
            raise RuntimeError("Canvas host must include Input and Output canvases.")

    with trace_span("mainwindow.build_workspace.canvas.state_service"):
        input_canvas_state_service = InputCanvasStateService(
            input_document=input_canvas.document,
            input_route_projector=input_canvas.route_projector,
            canvas_session_boundary=canvas_session_boundary,
            image_registry=canvas_image_registry,
        )
        output_canvas_state_service = OutputCanvasStateService(
            image_registry=canvas_image_registry,
        )
        output_canvas_focus_service = OutputCanvasFocusService(
            image_registry=canvas_image_registry,
        )
        output_navigation_session_service = OutputNavigationSessionService()
        output_generated_result_service = OutputGeneratedResultService(
            image_registry=canvas_image_registry,
            output_state_service=output_canvas_state_service,
            navigation_session_service=output_navigation_session_service,
        )
        output_canvas_timing_service = OutputCanvasTimingService(
            image_registry=canvas_image_registry,
        )
        output_projection_content_synchronizer = (
            output_canvas.create_projection_content_synchronizer(canvas_image_registry)
        )
        output_canvas_projection_coordinator = OutputCanvasProjectionCoordinator(
            image_registry=canvas_image_registry,
            output_canvas_state_service=output_canvas_state_service,
            output_canvas_focus_service=output_canvas_focus_service,
            output_navigation_session_service=output_navigation_session_service,
            canvas_session_boundary=canvas_session_boundary,
            content_synchronizer=output_projection_content_synchronizer,
            projection_sink=output_canvas,
        )
        workflow_canvas_projection_coordinator = WorkflowCanvasProjectionCoordinator(
            input_canvas_state_service=input_canvas_state_service,
            output_canvas_projection_coordinator=output_canvas_projection_coordinator,
        )

    with trace_span("mainwindow.build_workspace.canvas.container"):
        canvas_host_container = QWidget()
        container_layout = QVBoxLayout(canvas_host_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(cast(QWidget, canvas_host))
    return (
        canvas_host,
        input_canvas_state_service,
        output_canvas_state_service,
        output_canvas_focus_service,
        output_navigation_session_service,
        output_generated_result_service,
        output_canvas_timing_service,
        output_canvas_projection_coordinator,
        workflow_canvas_projection_coordinator,
        canvas_image_registry,
        output_floating_chrome_factory,
        canvas_host_container,
    )


def _build_progress_overlay(
    window: QWidget,
) -> tuple[QWidget, ProgressBar, ProgressBar]:
    """Build the floating stacked progress overlay shown under the menu row."""

    progress_overlay = QWidget(window)
    progress_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    progress_overlay.setStyleSheet("background: transparent;")
    progress_overlay.setFixedHeight(6)
    overlay_layout = QVBoxLayout(progress_overlay)
    overlay_layout.setContentsMargins(0, 0, 0, 0)
    overlay_layout.setSpacing(0)

    progress_strip = GenerationProgressStrip(progress_overlay)
    progress_strip.set_progress_visible(True)
    progress_strip.set_progress_active(True)
    overlay_layout.addWidget(progress_strip)
    setattr(progress_overlay, "generation_progress_strip", progress_strip)
    progress_overlay.hide()
    return (
        progress_overlay,
        progress_strip.workflow_bar,
        progress_strip.sampler_bar,
    )


def build_main_window_workspace(
    window: QMainWindow,
    *,
    canvas_execution_runtime: ExecutionRuntime,
    backdrop_mode: ShellBackdropMode | None = None,
    menu_container: QWidget,
    comfy_output_stream: TerminalOutputStream,
    output_preview_registry: OutputPreviewRegistry,
    open_single_external_editor: OutputSingleExternalEditor | None,
    open_all_external_editor: OutputAllExternalEditor | None,
    reveal_output_asset: OutputAssetReveal | None = None,
    configure_output_thumbnail_context: Callable[
        [CanvasImageRegistry, Callable[[], OutputCanvasProjection | None]],
        None,
    ]
    | None = None,
) -> MainWindowWorkspaceWidgets:
    """Build the MainWindow workspace scaffold and central layout."""

    trace_mark("mainwindow.build_workspace.start")
    with trace_span("mainwindow.build_workspace.workflow_tabbar"):
        (
            workflow_tab_service,
            workflow_session_service,
            workflow_tabbar,
        ) = _build_workflow_tabbar(window, menu_container, backdrop_mode)

    with trace_span("mainwindow.build_workspace.editor_shell_containers"):
        cube_stack_container = QStackedWidget(window)
        cube_stack_container.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        cube_stack_container.setFixedWidth(CUBE_STACK_EXPANDED_WIDTH)
        cube_stack_container.setContentsMargins(0, CUBE_STACK_TOP_INSET, 0, 0)
        editor_panel_container = QStackedWidget(window)
        workspace_top_row = QWidget(window)
        workspace_top_layout = QHBoxLayout(workspace_top_row)
        workspace_top_layout.setContentsMargins(0, 0, 0, 0)
        workspace_top_layout.setSpacing(0)
        workspace_top_layout.addWidget(cube_stack_container)
        workspace_top_layout.addWidget(editor_panel_container)
        workspace_top_layout.setStretch(0, 0)
        workspace_top_layout.setStretch(1, 1)
        editor_busy_overlay = EditorBusyOverlay(workspace_top_row)

    with trace_span("mainwindow.build_workspace.editor_output_splitter"):
        editor_output_container = QWidget(window)
        editor_output_layout = QVBoxLayout(editor_output_container)
        editor_output_layout.setContentsMargins(0, 0, 0, 0)
        editor_output_layout.setSpacing(0)

        editor_output_splitter = QSplitter(
            Qt.Orientation.Vertical,
            editor_output_container,
        )
        editor_output_splitter.setObjectName("EditorOutputSplitter")
        editor_output_splitter.setChildrenCollapsible(False)
        editor_output_splitter.setHandleWidth(1)

    with trace_span("mainwindow.build_workspace.comfy_output_panel"):
        comfy_output_panel = ComfyOutputPanel()
        comfy_output_panel.set_stream(comfy_output_stream)

    with trace_span("mainwindow.build_workspace.editor_output_layout"):
        editor_output_splitter.addWidget(workspace_top_row)
        editor_output_splitter.addWidget(comfy_output_panel)
        editor_output_splitter.setCollapsible(0, False)
        editor_output_splitter.setCollapsible(1, True)
        editor_output_splitter.setStretchFactor(0, 1)
        editor_output_splitter.setStretchFactor(1, 0)
        editor_output_layout.addWidget(editor_output_splitter)

    with trace_span("mainwindow.build_workspace.canvas_scaffold"):
        (
            canvas_host,
            input_canvas_state_service,
            output_canvas_state_service,
            output_canvas_focus_service,
            output_navigation_session_service,
            output_generated_result_service,
            output_canvas_timing_service,
            output_canvas_projection_coordinator,
            workflow_canvas_projection_coordinator,
            canvas_image_registry,
            output_floating_chrome_factory,
            canvas_host_container,
        ) = _build_canvas_scaffold(
            window,
            canvas_execution_runtime=canvas_execution_runtime,
            output_preview_registry=output_preview_registry,
            open_single_external_editor=open_single_external_editor,
            open_all_external_editor=open_all_external_editor,
            reveal_output_asset=reveal_output_asset,
        )
        if configure_output_thumbnail_context is not None:
            configure_output_thumbnail_context(
                canvas_image_registry,
                lambda: _output_projection_for_canvas_host(canvas_host),
            )

    with trace_span("mainwindow.build_workspace.central_layout"):
        central = QWidget(window)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        main_content = WorkspaceBodyMaterialSurface(
            backdrop_mode=backdrop_mode,
            parent=window,
        )
        main_content_layout = QHBoxLayout(main_content)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(editor_output_container)
        splitter.addWidget(canvas_host_container)
        side_panel_host = WorkspaceSidePanelHost()
        splitter.addWidget(side_panel_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        workflow_workspace_page = QWidget(window)
        workflow_workspace_layout = QHBoxLayout(workflow_workspace_page)
        workflow_workspace_layout.setContentsMargins(0, 0, 0, 0)
        workflow_workspace_layout.setSpacing(0)
        workflow_workspace_layout.addWidget(splitter)

        settings_workspace_page = QWidget(window)
        settings_workspace_layout = QHBoxLayout(settings_workspace_page)
        settings_workspace_layout.setContentsMargins(0, 0, 0, 0)
        settings_workspace_layout.setSpacing(0)

        workspace_route_container = QStackedWidget(window)
        workspace_route_container.addWidget(workflow_workspace_page)
        workspace_route_container.addWidget(settings_workspace_page)
        workspace_route_container.setCurrentWidget(workflow_workspace_page)

        main_content_layout.addWidget(workspace_route_container)
        central_layout.addWidget(main_content)
        main_content.set_cube_stack_region_widget(cube_stack_container)

    def _apply_theme_styles() -> None:
        workflow_hover_rgba = (
            "rgba(100, 100, 100, 0.16)" if isDarkTheme() else "rgba(0, 0, 0, 0.08)"
        )
        workflow_pressed_rgba = (
            "rgba(80, 80, 80, 0.24)" if isDarkTheme() else "rgba(0, 0, 0, 0.14)"
        )
        workflow_tabbar.setStyleSheet(
            f"""
            QWidget {{
                background: transparent;
                border: none;
            }}
            TransparentToolButton {{
                padding: 0 2px;
                border-radius: 4px;
            }}
            TransparentToolButton:hover {{
                background: {workflow_hover_rgba};
            }}
            TransparentToolButton:pressed {{
                background: {workflow_pressed_rgba};
            }}
            """
        )
        editor_output_splitter.setStyleSheet(
            f"""
            QSplitter#EditorOutputSplitter {{
                background-color: transparent;
            }}
            QSplitter#EditorOutputSplitter::handle:vertical {{
                background-color: {splitter_handle_rgba()};
                height: 1px;
            }}
            """
        )
        splitter.setStyleSheet(
            f"""
            QSplitter {{
                background-color: transparent;
            }}
            QSplitter::handle {{
                background-color: {splitter_handle_rgba()};
                width: 4px;
            }}
            """
        )

    with trace_span("mainwindow.build_workspace.window_install"):
        window.setCentralWidget(central)
        window.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
        )

    with trace_span("mainwindow.build_workspace.progress_overlay"):
        (
            progress_overlay,
            workflow_overlay_bar,
            sampler_overlay_bar,
        ) = _build_progress_overlay(window)
    with trace_span("mainwindow.build_workspace.theme_styles"):
        _apply_theme_styles()
        connect_theme_refresh(main_content, _apply_theme_styles)
    trace_mark("mainwindow.build_workspace.end")

    return MainWindowWorkspaceWidgets(
        workflow_tab_service=workflow_tab_service,
        workflow_session_service=workflow_session_service,
        workflow_tabbar=workflow_tabbar,
        workspace_body_material_surface=main_content,
        workspace_route_container=workspace_route_container,
        workflow_workspace_page=workflow_workspace_page,
        settings_workspace_page=settings_workspace_page,
        settings_workspace_layout=settings_workspace_layout,
        cube_stack_container=cube_stack_container,
        editor_output_container=editor_output_container,
        editor_output_splitter=editor_output_splitter,
        editor_panel_container=editor_panel_container,
        editor_busy_overlay=editor_busy_overlay,
        comfy_output_panel=comfy_output_panel,
        canvas_host=canvas_host,
        input_canvas_state_service=input_canvas_state_service,
        output_canvas_state_service=output_canvas_state_service,
        output_canvas_focus_service=output_canvas_focus_service,
        output_navigation_session_service=output_navigation_session_service,
        output_generated_result_service=output_generated_result_service,
        output_canvas_timing_service=output_canvas_timing_service,
        output_canvas_projection_coordinator=output_canvas_projection_coordinator,
        workflow_canvas_projection_coordinator=workflow_canvas_projection_coordinator,
        canvas_image_registry=canvas_image_registry,
        output_floating_chrome_factory=output_floating_chrome_factory,
        canvas_host_container=canvas_host_container,
        side_panel_host=side_panel_host,
        splitter=splitter,
        progress_overlay=progress_overlay,
        workflow_overlay_bar=workflow_overlay_bar,
        sampler_overlay_bar=sampler_overlay_bar,
    )


def _output_projection_for_canvas_host(
    canvas_host: object,
) -> OutputCanvasProjection | None:
    """Return the current Output projection from the composed canvas host."""

    canvas_for = getattr(canvas_host, "canvas_for", None)
    if not callable(canvas_for):
        return None
    output_canvas = canvas_for("Output")
    projection = getattr(output_canvas, "_output_projection", None)
    return projection if isinstance(projection, OutputCanvasProjection) else None


__all__ = [
    "MainWindowWorkspaceWidgets",
    "WorkspaceSidePanelHost",
    "build_main_window_workspace",
]
