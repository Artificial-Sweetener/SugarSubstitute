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

"""Contract tests for extracted MainWindow workspace construction."""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


class _Widget:
    """Generic widget stub implementing the builder-facing Qt API."""

    def __init__(self, *_args, **_kwargs) -> None:
        self._parent = _args[0] if _args and isinstance(_args[0], _Widget) else None
        self._layout = None
        self.hidden = False
        self.visible = False
        self.object_name = None
        self.style = None
        self.attributes: list[object] = []
        self.children: list[object] = []
        self.fixed_width: int | None = None
        self.size_policy: tuple[object, object] | None = None
        self.contents_margins: tuple[object, ...] | None = None
        self.event_filters: list[object] = []
        self.geometry: object | None = None
        if self._parent is not None:
            self._parent.children.append(self)

    def width(self) -> int:
        """Return a deterministic stub width."""

        return 800

    def height(self) -> int:
        """Return a deterministic stub height."""

        return 600

    def setLayout(self, layout: object) -> None:
        """Store the widget layout."""

        self._layout = layout

    def layout(self) -> object | None:
        """Return the stored layout."""

        return self._layout

    def setObjectName(self, name: str) -> None:
        """Record the assigned object name."""

        self.object_name = name

    def setStyleSheet(self, style: str) -> None:
        """Record stylesheet updates."""

        self.style = style

    def setAttribute(self, attribute: object) -> None:
        """Record setAttribute calls."""

        self.attributes.append(attribute)

    def setFocusPolicy(self, _policy: object) -> None:
        """Accept focus policy updates."""

    def setFocus(self, _reason: object = None) -> None:
        """Accept focus requests."""

    def installEventFilter(self, event_filter: object) -> None:
        """Record installed event filters."""

        self.event_filters.append(event_filter)

    def eventFilter(self, _watched: object, _event: object) -> bool:
        """Fallback event filter implementation."""

        return False

    def parent(self) -> object | None:
        """Return parent object."""

        return self._parent

    def parentWidget(self) -> object | None:
        """Return parent widget."""

        return self._parent

    def rect(self) -> object:
        """Return a simple geometry token."""

        return ("rect", id(self))

    def setGeometry(self, *geometry: object) -> None:
        """Record widget geometry."""

        self.geometry = geometry[0] if len(geometry) == 1 else geometry

    def raise_(self) -> None:
        """Accept stacking requests."""

    def show(self) -> None:
        """Record visible state."""

        self.hidden = False
        self.visible = True

    def isVisible(self) -> bool:
        """Return recorded visible state."""

        return self.visible and not self.hidden

    def setFixedHeight(self, _height: int) -> None:
        """Accept fixed-height configuration."""

    def setFixedWidth(self, width: int) -> None:
        """Record fixed-width configuration."""

        self.fixed_width = width

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record size-policy configuration."""

        self.size_policy = (horizontal, vertical)

    def setContentsMargins(self, *margins: object) -> None:
        """Record widget-owned contents margins."""

        self.contents_margins = margins

    def hide(self) -> None:
        """Record hidden state."""

        self.hidden = True
        self.visible = False


class _Label(_Widget):
    """Label stub recording text and alignment state."""

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__(*_args, **_kwargs)
        self.text_value = ""

    def setAlignment(self, alignment: object) -> None:
        """Record alignment."""

        self.alignment = alignment

    def setMinimumWidth(self, width: int) -> None:
        """Record minimum width."""

        self.minimum_width = width

    def setText(self, text: str) -> None:
        """Record label text."""

        self.text_value = text

    def sizeHint(self) -> object:  # noqa: N802
        """Return a deterministic label size hint."""

        return SimpleNamespace(
            width=lambda: max(1, len(self.text_value) * 8),
            height=lambda: 20,
        )

    def fontMetrics(self) -> object:  # noqa: N802
        """Return a deterministic font-metrics stub."""

        return SimpleNamespace(horizontalAdvance=lambda text: max(1, len(text) * 8))


class _Layout:
    """Layout stub recording inserted widgets and stretch factors."""

    def __init__(self, parent: object | None = None, *_args, **_kwargs) -> None:
        self.widgets: list[object] = []
        self.stretches: list[tuple[int, int]] = []
        self.contents_margins: tuple[object, ...] | None = None
        if isinstance(parent, _Widget):
            parent.setLayout(self)

    def setContentsMargins(self, *margins: object) -> None:
        """Record layout contents margins."""

        self.contents_margins = margins

    def setSpacing(self, _spacing: int) -> None:
        """Accept spacing updates."""

    def addWidget(self, widget: object, *_args, **_kwargs) -> None:
        """Append one widget."""

        self.widgets.append(widget)

    def insertWidget(self, index: int, widget: object) -> None:
        """Insert one widget."""

        self.widgets.insert(index, widget)

    def addLayout(self, layout: object) -> None:
        """Append one nested layout."""

        self.widgets.append(layout)

    def setStretch(self, index: int, stretch: int) -> None:
        """Record stretch assignments."""

        self.stretches.append((index, stretch))

    def count(self) -> int:
        """Return number of tracked items."""

        return len(self.widgets)


class _Splitter(_Widget):
    """Splitter stub recording child widgets and stretch factors."""

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.widgets: list[object] = []
        self.stretch_factors: list[tuple[int, int]] = []
        self.collapsible: list[tuple[int, bool]] = []
        self.handle_width: int | None = None
        self.sizes: list[int] = []

    def setChildrenCollapsible(self, _value: bool) -> None:
        """Accept collapsible configuration."""

    def setCollapsible(self, index: int, value: bool) -> None:
        """Record per-child collapsible configuration."""

        if index >= len(self.widgets):
            raise AssertionError("setCollapsible called before splitter child exists")
        self.collapsible.append((index, value))

    def setHandleWidth(self, width: int) -> None:
        """Record handle-width configuration."""

        self.handle_width = width

    def addWidget(self, widget: object) -> None:
        """Append a splitter child."""

        self.widgets.append(widget)

    def setStretchFactor(self, index: int, factor: int) -> None:
        """Record splitter stretch configuration."""

        self.stretch_factors.append((index, factor))

    def setSizes(self, sizes: list[int]) -> None:
        """Record requested splitter sizes."""

        self.sizes = list(sizes)


class _StackedWidget(_Widget):
    """Stacked widget stub."""

    def __init__(self, *_args, **_kwargs) -> None:
        """Create a stacked-widget recorder."""

        super().__init__(*_args, **_kwargs)
        self.widgets: list[object] = []
        self.current_widget: object | None = None

    def addWidget(self, widget: object) -> None:
        """Append one stacked page."""

        self.widgets.append(widget)

    def setCurrentWidget(self, widget: object) -> None:
        """Record the selected stacked page."""

        self.current_widget = widget


class _ProgressBar(_Widget):
    """Progress-bar stub storing numeric configuration."""

    def setMaximum(self, value: int) -> None:
        """Record max value."""

        self.maximum = value

    def setMinimum(self, value: int) -> None:
        """Record min value."""

        self.minimum = value

    def setValue(self, value: int) -> None:
        """Record current value."""

        self.value = value

    def setFormat(self, value: str) -> None:
        """Record display format."""

        self.format = value

    def setCustomBackgroundColor(self, light: object, dark: object) -> None:
        """Record custom unfilled-background colors."""

        self.custom_background = (light, dark)


class _Window(_Widget):
    """MainWindow stub tracking central widget and dock options."""

    AllowTabbedDocks = 1
    AnimatedDocks = 2
    AllowNestedDocks = 4
    DockOption = SimpleNamespace(
        AllowTabbedDocks=AllowTabbedDocks,
        AnimatedDocks=AnimatedDocks,
        AllowNestedDocks=AllowNestedDocks,
    )

    def setCentralWidget(self, widget: object) -> None:
        """Record central widget assignment."""

        self.central_widget = widget

    def setDockOptions(self, options: object) -> None:
        """Record dock options."""

        self.dock_options = options


class _TabBar(_Widget):
    """Workflow-tab bar stub recording initial tab setup."""

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.tabs: list[tuple[str, str]] = []
        self.current_index: int | None = None

    def addTab(self, route_key: str, text: str) -> None:
        """Record one added workflow tab."""

        self.tabs.append((route_key, text))

    def setMovable(self, _value: bool) -> None:
        """Accept movable configuration."""

    def setTabMaximumWidth(self, _width: int) -> None:
        """Accept tab-width configuration."""

    def setCloseButtonDisplayMode(self, _mode: object) -> None:
        """Accept close-button mode configuration."""

    def setMinimumHeight(self, _height: int) -> None:
        """Accept min-height configuration."""

    def setCurrentIndex(self, index: int) -> None:
        """Record current index."""

        self.current_index = index


class _ComfyOutputPanel(_Widget):
    """Output-panel stub recording stream binding and visibility state."""

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__()
        self.stream = None
        self.hide()

    def set_stream(self, stream: object) -> None:
        """Record the assigned output stream."""

        self.stream = stream


def _install_stubs() -> None:
    """Install lightweight import stubs for workspace construction."""

    for module_name in list(sys.modules):
        if module_name.startswith("qfluentwidgets") or module_name.startswith(
            "PySide6"
        ):
            sys.modules.pop(module_name, None)

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = SimpleNamespace(
        Horizontal="horizontal",
        Vertical="vertical",
        Orientation=SimpleNamespace(
            Horizontal="horizontal",
            Vertical="vertical",
        ),
        WA_TransparentForMouseEvents="transparent",
        FocusPolicy=SimpleNamespace(StrongFocus="strong-focus"),
        WidgetAttribute=SimpleNamespace(
            WA_StyledBackground="styled-background",
            WA_TransparentForMouseEvents="transparent",
        ),
        AlignmentFlag=SimpleNamespace(
            AlignCenter=0,
            AlignLeft=1,
            AlignVCenter=2,
        ),
        FocusReason=SimpleNamespace(OtherFocusReason="other-focus"),
    )
    qtcore.QEvent = type(
        "QEvent",
        (),
        {"Type": SimpleNamespace(Resize="resize")},
    )
    qtcore.QObject = _Widget

    class _Timer:
        def __init__(self, *_args, **_kwargs) -> None:
            self.interval = 0
            self.active = False
            self.timeout = SimpleNamespace(
                connect=lambda callback: setattr(self, "callback", callback)
            )

        def setInterval(self, interval: int) -> None:
            self.interval = interval

        def start(self) -> None:
            self.active = True

        def stop(self) -> None:
            self.active = False

        def isActive(self) -> bool:
            return self.active

    qtcore.QTimer = _Timer
    sys.modules["PySide6.QtCore"] = qtcore

    qtgui = types.ModuleType("PySide6.QtGui")

    class _QColor:
        def __init__(self, r: int, g: int, b: int, a: int) -> None:
            self.rgba = (r, g, b, a)

    qtgui.QColor = _QColor
    qtgui.QHideEvent = type("QHideEvent", (), {})
    qtgui.QPaintEvent = type("QPaintEvent", (), {})
    qtgui.QResizeEvent = type("QResizeEvent", (), {})
    qtgui.QShowEvent = type("QShowEvent", (), {})
    sys.modules["PySide6.QtGui"] = qtgui

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = SimpleNamespace(
        setOverrideCursor=lambda _cursor: None,
        restoreOverrideCursor=lambda: None,
    )
    qtwidgets.QWidget = _Widget
    qtwidgets.QLabel = _Label
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QMainWindow = _Window
    qtwidgets.QSplitter = _Splitter
    qtwidgets.QStackedWidget = _StackedWidget
    qtwidgets.QSizePolicy = SimpleNamespace(
        Policy=SimpleNamespace(Fixed="fixed", Expanding="expanding")
    )
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6"] = types.ModuleType("PySide6")

    qfw = types.ModuleType("qfluentwidgets")
    qfw.ProgressBar = _ProgressBar
    sys.modules["qfluentwidgets"] = qfw

    workflows_module = types.ModuleType("substitute.application.workflows")
    workflows_module.WorkflowTabService = type("WorkflowTabService", (), {})
    workflows_module.WorkflowSessionService = type(
        "WorkflowSessionService",
        (),
        {"__init__": lambda self: setattr(self, "active_workflow_id", "wf-1")},
    )

    class _OutputCanvasProjectionCoordinator:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _InputCanvasStateService:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _OutputProjectionCatalogWarmer:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _OutputProjectionPayloadHydrator:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _WorkflowCanvasProjectionCoordinator:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    workflows_module.InputCanvasStateService = _InputCanvasStateService
    workflows_module.OutputCanvasProjectionCoordinator = (
        _OutputCanvasProjectionCoordinator
    )
    workflows_module.OutputProjectionCatalogWarmer = _OutputProjectionCatalogWarmer
    workflows_module.OutputProjectionPayloadHydrator = _OutputProjectionPayloadHydrator
    workflows_module.WorkflowCanvasProjectionCoordinator = (
        _WorkflowCanvasProjectionCoordinator
    )
    sys.modules["substitute.application.workflows"] = workflows_module

    canvas_module = types.ModuleType("substitute.presentation.canvas")
    canvas_module.build_linked_group = lambda members: ("linked", members)
    chrome_factories: list[object] = []

    class _OutputFloatingChromeFactory:
        """Capture Output floating chrome factory usage in workspace tests."""

        def __init__(self) -> None:
            """Initialize registry update capture."""

            self.titlebar_registries: list[object] = []
            self.progress_registries: list[object] = []

        def set_titlebar_control_registry(self, registry: object) -> None:
            """Record titlebar registry updates."""

            self.titlebar_registries.append(registry)

        def set_progress_strip_registry(self, registry: object) -> None:
            """Record progress registry updates."""

            self.progress_registries.append(registry)

    def create_output_floating_chrome_factory() -> object:
        """Return one Output-owned chrome factory for the canvas host."""

        factory = _OutputFloatingChromeFactory()
        chrome_factories.append(factory)
        return factory

    canvas_module.create_output_floating_chrome_factory = (
        create_output_floating_chrome_factory
    )
    output_catalog = ("shared-catalog", "output-pane")

    def create_canvas_tabs(**kwargs: object) -> object:
        """Return canvas tabs and capture the injected Output chrome factory."""

        return SimpleNamespace(
            create_kwargs=kwargs,
            canvas_map={
                "Input": SimpleNamespace(
                    pane="input-pane",
                    route_projector="input-projector",
                ),
                "Output": SimpleNamespace(
                    pane="output-pane",
                    qpane_catalog=output_catalog,
                    route_projector="output-projector",
                ),
            },
            output_floating_chrome_factory=kwargs.get("output_floating_chrome_factory"),
        )

    class _OutputLinkedGroupPresenter:
        def __init__(self, pane: object) -> None:
            self.pane = pane

    canvas_module.create_canvas_tabs = create_canvas_tabs
    canvas_module.OutputLinkedGroupPresenter = _OutputLinkedGroupPresenter
    sys.modules["substitute.presentation.canvas"] = canvas_module
    canvas_qpane_module = types.ModuleType("substitute.presentation.canvas.qpane")
    canvas_qpane_module.CanvasPaneCatalog = lambda pane: ("catalog", pane)
    canvas_qpane_module.InputQPaneRouteAdapter = lambda pane: ("input-adapter", pane)
    canvas_qpane_module.OutputQPaneRouteAdapter = lambda pane: ("output-adapter", pane)
    canvas_qpane_module.InputRouteProjector = lambda adapter, session_boundary: (
        "input-projector",
        adapter,
        session_boundary,
    )
    canvas_qpane_module.OutputRouteProjector = lambda adapter, session_boundary: (
        "output-projector",
        adapter,
        session_boundary,
    )
    sys.modules["substitute.presentation.canvas.qpane"] = canvas_qpane_module

    workflow_tabs_module = types.ModuleType(
        "substitute.presentation.workflows.workflow_tabs_view"
    )
    workflow_tabs_module.TabBar = _TabBar
    workflow_tabs_module.TabCloseButtonDisplayMode = SimpleNamespace(
        ON_HOVER="on-hover"
    )
    sys.modules["substitute.presentation.workflows.workflow_tabs_view"] = (
        workflow_tabs_module
    )

    cube_stack_module = types.ModuleType(
        "substitute.presentation.workflows.cube_stack_view"
    )
    cube_stack_module.CUBE_STACK_EXPANDED_WIDTH = 206
    sys.modules["substitute.presentation.workflows.cube_stack_view"] = cube_stack_module

    output_panel_module = types.ModuleType(
        "substitute.presentation.shell.comfy_output_panel"
    )
    output_panel_module.ComfyOutputPanel = _ComfyOutputPanel
    sys.modules["substitute.presentation.shell.comfy_output_panel"] = (
        output_panel_module
    )

    chrome_style_module = types.ModuleType("substitute.presentation.shell.chrome_style")
    chrome_style_module.BODY_MATERIAL_SURFACE_OBJECT_NAME = (
        "SubstituteBodyMaterialSurface"
    )
    chrome_style_module.CUBE_STACK_TOP_INSET = 6
    chrome_style_module.connect_theme_refresh = lambda *_args, **_kwargs: None
    chrome_style_module.splitter_handle_rgba = lambda: "rgba(0, 0, 0, 0)"
    sys.modules["substitute.presentation.shell.chrome_style"] = chrome_style_module

    workspace_material_module = types.ModuleType(
        "substitute.presentation.shell.workspace_body_material_surface"
    )

    class _WorkspaceBodyMaterialSurface(_Widget):
        """Workspace material-surface stub recording cube-stack registration."""

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.backdrop_mode = kwargs.get("backdrop_mode")
            self.setObjectName("SubstituteBodyMaterialSurface")
            self.cube_stack_region_widget: object | None = None
            self.cube_stack_wash_opacity_values: list[float] = [1.0]

        def set_cube_stack_region_widget(self, widget: object | None) -> None:
            """Record the cube-stack region widget."""

            self.cube_stack_region_widget = widget

        def set_cube_stack_wash_opacity(self, opacity: float) -> None:
            """Record cube-stack wash opacity updates."""

            self.cube_stack_wash_opacity_values.append(opacity)

    workspace_material_module.WorkspaceBodyMaterialSurface = (
        _WorkspaceBodyMaterialSurface
    )
    sys.modules["substitute.presentation.shell.workspace_body_material_surface"] = (
        workspace_material_module
    )

    window_frame_module = types.ModuleType("substitute.presentation.shell.window_frame")
    window_frame_module.ShellBackdropMode = type("ShellBackdropMode", (), {})
    window_frame_module.titlebar_menu_content_insert_index = lambda _container: 0
    sys.modules["substitute.presentation.shell.window_frame"] = window_frame_module

    output_stream_module = types.ModuleType(
        "sugarsubstitute_shared.presentation.terminal.output_stream"
    )
    output_stream_module.TerminalOutputStream = type("TerminalOutputStream", (), {})
    sys.modules["sugarsubstitute_shared.presentation.terminal.output_stream"] = (
        output_stream_module
    )


def _preserve_stubbed_modules() -> dict[str, types.ModuleType]:
    """Capture real modules that the workspace stubs temporarily replace."""

    return {
        module_name: module
        for module_name, module in sys.modules.items()
        if module_name == "qfluentwidgets"
        or module_name.startswith("qfluentwidgets.")
        or module_name == "PySide6"
        or module_name.startswith("PySide6.")
        or module_name
        in {
            "substitute.presentation.shell.main_window_workspace",
            "substitute.presentation.shell.editor_busy_overlay",
            "substitute.application.workflows",
            "substitute.presentation.canvas",
            "substitute.presentation.workflows.cube_stack_view",
            "substitute.presentation.workflows.workflow_tabs_view",
            "substitute.presentation.shell.chrome_style",
            "substitute.presentation.shell.comfy_output_panel",
            "substitute.presentation.shell.generation_progress_strip",
            "substitute.presentation.shell.window_frame",
            "substitute.presentation.shell.workspace_body_material_surface",
            "sugarsubstitute_shared.presentation.terminal.output_stream",
        }
    }


def _restore_stubbed_modules(preserved_modules: dict[str, types.ModuleType]) -> None:
    """Remove temporary stubs and restore previously loaded real modules."""

    for module_name in list(sys.modules):
        if module_name == "qfluentwidgets" or module_name.startswith("qfluentwidgets."):
            sys.modules.pop(module_name, None)
        if module_name == "PySide6" or module_name.startswith("PySide6."):
            sys.modules.pop(module_name, None)
        if module_name in {
            "substitute.presentation.shell.main_window_workspace",
            "substitute.presentation.shell.editor_busy_overlay",
            "substitute.application.workflows",
            "substitute.presentation.canvas",
            "substitute.presentation.workflows.cube_stack_view",
            "substitute.presentation.workflows.workflow_tabs_view",
            "substitute.presentation.shell.chrome_style",
            "substitute.presentation.shell.comfy_output_panel",
            "substitute.presentation.shell.generation_progress_strip",
            "substitute.presentation.shell.window_frame",
            "substitute.presentation.shell.workspace_body_material_surface",
            "sugarsubstitute_shared.presentation.terminal.output_stream",
        }:
            sys.modules.pop(module_name, None)
    sys.modules.update(preserved_modules)


def _import_module():
    """Import the workspace builder module under lightweight stubs."""

    preserved_modules = _preserve_stubbed_modules()
    _install_stubs()
    sys.modules.pop("substitute.presentation.shell.main_window_workspace", None)
    sys.modules.pop("substitute.presentation.shell.editor_busy_overlay", None)
    sys.modules.pop("substitute.presentation.shell.generation_progress_strip", None)
    try:
        module = importlib.import_module(
            "substitute.presentation.shell.main_window_workspace"
        )
    finally:
        _restore_stubbed_modules(preserved_modules)
    return module


def test_build_main_window_workspace_defers_workflow_tabs_and_wires_central_layout() -> (
    None
):
    """Workspace construction should leave visible workflow tabs to hydration."""

    mod = _import_module()
    window = _Window()
    menu_container = _Widget()
    menu_layout = _Layout()
    menu_container.setLayout(menu_layout)
    output_preview_registry = object()

    widgets = mod.build_main_window_workspace(
        window,
        menu_container=menu_container,
        comfy_output_stream=object(),
        output_preview_registry=output_preview_registry,
        open_single_external_editor=object(),
        open_all_external_editor=object(),
    )

    assert widgets.workflow_tabbar.tabs == []
    assert widgets.workflow_tabbar.current_index is None
    assert "min-height: 10px" not in widgets.workflow_tabbar.style
    assert "max-height: 10px" not in widgets.workflow_tabbar.style
    assert window.central_widget is not None
    assert window.dock_options is not None
    assert widgets.input_canvas_state_service.kwargs["input_pane"] == "input-pane"
    assert widgets.input_canvas_state_service.kwargs["input_catalog"] == (
        "catalog",
        "input-pane",
    )
    assert (
        widgets.workflow_canvas_projection_coordinator.kwargs[
            "input_canvas_state_service"
        ]
        is widgets.input_canvas_state_service
    )
    assert (
        widgets.workflow_canvas_projection_coordinator.kwargs[
            "output_canvas_projection_coordinator"
        ]
        is widgets.output_canvas_projection_coordinator
    )
    assert (
        widgets.output_canvas_projection_coordinator.kwargs["output_route_projector"]
        == "output-projector"
    )
    assert (
        widgets.output_canvas_projection_coordinator.kwargs["projection_sink"]
        is widgets.canvas_tabs.canvas_map["Output"]
    )
    assert (
        widgets.output_canvas_projection_coordinator.kwargs["linked_group_sink"].pane
        == "output-pane"
    )
    assert widgets.output_canvas_projection_coordinator.kwargs["catalog_warmer"].kwargs[
        "output_catalog"
    ] == (
        "shared-catalog",
        "output-pane",
    )
    assert (
        widgets.canvas_tabs.output_floating_chrome_factory
        is widgets.output_floating_chrome_factory
    )
    assert (
        widgets.canvas_tabs.create_kwargs["output_preview_registry"]
        is output_preview_registry
    )
    assert not hasattr(widgets.canvas_tabs, "set_generation_titlebar_control_registry")
    assert not hasattr(widgets.canvas_tabs, "set_generation_progress_strip_registry")
    assert widgets.progress_overlay.hidden is True
    assert widgets.editor_busy_overlay.hidden is True
    assert widgets.cube_stack_container.fixed_width == mod.CUBE_STACK_EXPANDED_WIDTH
    assert widgets.cube_stack_container.size_policy == ("fixed", "expanding")
    assert widgets.cube_stack_container.contents_margins == (0, 6, 0, 0)
    assert widgets.comfy_output_panel.hidden is True
    assert widgets.workflow_overlay_bar.custom_background[0].rgba == (0, 0, 0, 0)
    assert widgets.workflow_overlay_bar.custom_background[1].rgba == (0, 0, 0, 0)
    assert widgets.sampler_overlay_bar.custom_background[0].rgba == (0, 0, 0, 0)
    assert widgets.sampler_overlay_bar.custom_background[1].rgba == (0, 0, 0, 0)
    assert (
        widgets.progress_overlay.generation_progress_strip.workflow_bar
        is widgets.workflow_overlay_bar
    )
    assert (
        widgets.progress_overlay.generation_progress_strip.sampler_bar
        is widgets.sampler_overlay_bar
    )
    assert "#09f" in widgets.workflow_overlay_bar.style
    assert "#F59E0B" in widgets.sampler_overlay_bar.style

    main_content = window.central_widget.layout().widgets[0]
    assert main_content.object_name == "SubstituteBodyMaterialSurface"
    assert widgets.workspace_body_material_surface is main_content
    assert main_content.cube_stack_region_widget is widgets.cube_stack_container
    assert main_content.cube_stack_wash_opacity_values == [1.0]
    main_content_layout = main_content.layout()
    assert main_content_layout.contents_margins == (0, 0, 0, 0)
    assert main_content_layout.widgets == [widgets.workspace_route_container]
    assert widgets.workspace_route_container.widgets == [
        widgets.workflow_workspace_page,
        widgets.settings_workspace_page,
    ]
    assert widgets.workspace_route_container.current_widget is (
        widgets.workflow_workspace_page
    )
    assert widgets.workflow_workspace_page.layout().widgets == [widgets.splitter]
    assert widgets.workflow_workspace_page.layout().contents_margins == (0, 0, 0, 0)
    assert widgets.settings_workspace_page.layout().widgets == []
    assert widgets.settings_workspace_page.layout().contents_margins == (0, 0, 0, 0)
    assert widgets.splitter.widgets[0] is widgets.editor_output_container
    editor_output_splitter = widgets.editor_output_container.layout().widgets[0]
    assert widgets.editor_output_splitter is editor_output_splitter
    assert editor_output_splitter.widgets[0].layout().widgets == [
        widgets.cube_stack_container,
        widgets.editor_panel_container,
    ]
    workspace_top_row = editor_output_splitter.widgets[0]
    assert widgets.editor_busy_overlay.parentWidget() is workspace_top_row
    assert widgets.editor_busy_overlay.geometry == workspace_top_row.rect()
    assert workspace_top_row.layout().widgets == [
        widgets.cube_stack_container,
        widgets.editor_panel_container,
    ]
    assert widgets.editor_output_container.layout().widgets == [
        editor_output_splitter,
    ]
    assert editor_output_splitter.widgets == [
        workspace_top_row,
        widgets.comfy_output_panel,
    ]
    assert editor_output_splitter.collapsible == [(0, False), (1, True)]
