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

"""Tests for shell layout controller route chrome mutations."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workspace_snapshot.models import (
    CanvasLayoutSnapshot,
    FloatingCanvasWindowSnapshot,
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
)
from substitute.presentation.shell.shell_layout_controller import ShellLayoutController
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)


class _MaterialSurface:
    """Record cube-stack material region assignments."""

    def __init__(self) -> None:
        """Create an empty material-region recorder."""

        self.regions: list[object | None] = []

    def set_cube_stack_region_widget(self, widget: object | None) -> None:
        """Record the widget assigned as the cube-stack material region."""

        self.regions.append(widget)


class _Button:
    """Record enabled states applied to a shell button."""

    def __init__(self) -> None:
        """Create an empty enabled-state recorder."""

        self.enabled: list[bool] = []

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Record one Qt-style enabled-state mutation."""

        self.enabled.append(enabled)


class _VisibilityWidget:
    """Record visibility states applied to a shell widget."""

    def __init__(self) -> None:
        """Create an empty visibility recorder."""

        self.visible: list[bool] = []

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record one Qt-style visibility mutation."""

        self.visible.append(visible)


class _FallbackSearchWidget:
    """Expose show/hide fallback methods without setVisible."""

    def __init__(self) -> None:
        """Create an empty fallback visibility recorder."""

        self.calls: list[str] = []

    def show(self) -> None:
        """Record one show request."""

        self.calls.append("show")

    def hide(self) -> None:
        """Record one hide request."""

        self.calls.append("hide")


class _AppOrbMenu:
    """Record workflow file-action availability."""

    def __init__(self) -> None:
        """Create an empty file-action availability recorder."""

        self.enabled: list[bool] = []

    def set_workflow_file_actions_enabled(self, enabled: bool) -> None:
        """Record one file-action availability mutation."""

        self.enabled.append(enabled)


class _Splitter:
    """Record splitter sizes applied by layout controller operations."""

    def __init__(self, sizes: list[int]) -> None:
        """Create a splitter double with initial sizes."""

        self._sizes = sizes
        self.set_size_calls: list[list[int]] = []

    def sizes(self) -> list[int]:
        """Return the current splitter sizes."""

        return list(self._sizes)

    def setSizes(self, sizes: list[int]) -> None:  # noqa: N802
        """Record and apply one Qt-style splitter size update."""

        self.set_size_calls.append(list(sizes))
        self._sizes = list(sizes)


class _IndexedSplitter(_Splitter):
    """Expose splitter widget indexes for width-transfer tests."""

    def __init__(self, widgets: list[object], sizes: list[int]) -> None:
        """Create an indexed splitter double."""

        super().__init__(sizes)
        self._widgets = list(widgets)

    def indexOf(self, widget: object) -> int:  # noqa: N802
        """Return the index for one splitter widget."""

        try:
            return self._widgets.index(widget)
        except ValueError:
            return -1


class _StackContainer:
    """Record cube-stack container width changes."""

    def __init__(self, width: int) -> None:
        """Create a container double with one initial width."""

        self._width = width
        self.fixed_widths: list[int] = []

    def width(self) -> int:
        """Return the current container width."""

        return self._width

    def setFixedWidth(self, width: int) -> None:  # noqa: N802
        """Record and apply one fixed-width request."""

        self.fixed_widths.append(width)
        self._width = width


class _RecordingCubeStack:
    """Record compact values applied to one cube stack."""

    def __init__(self) -> None:
        """Create an empty compact-state recorder."""

        self.compact_values: list[bool] = []

    def setCompact(self, compact: bool) -> None:  # noqa: N802
        """Record one compact-state application."""

        self.compact_values.append(compact)


class _ModeButton:
    """Record cube-stack mode button synchronization."""

    def __init__(self) -> None:
        """Create an empty button-state recorder."""

        self.blocked = False
        self.checked_values: list[tuple[bool, bool]] = []
        self.icons: list[object] = []
        self.tooltips: list[str] = []

    def blockSignals(self, blocked: bool) -> bool:  # noqa: N802
        """Record signal-block state and return the previous value."""

        previous = self.blocked
        self.blocked = blocked
        return previous

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """Record one checked-state update with current signal-block state."""

        self.checked_values.append((checked, self.blocked))

    def setIcon(self, icon: object) -> None:  # noqa: N802
        """Record one icon update."""

        self.icons.append(icon)

    def setToolTip(self, tooltip: str) -> None:  # noqa: N802
        """Record one tooltip update."""

        self.tooltips.append(tooltip)


class _Geometry:
    """Expose Qt-style geometry accessors for snapshot tests."""

    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        """Store geometry values returned by Qt-style accessors."""

        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def x(self) -> int:
        """Return the stored x coordinate."""

        return self._x

    def y(self) -> int:
        """Return the stored y coordinate."""

        return self._y

    def width(self) -> int:
        """Return the stored width."""

        return self._width

    def height(self) -> int:
        """Return the stored height."""

        return self._height


class _Window:
    """Expose Qt-style window state for snapshot tests."""

    def __init__(
        self,
        geometry: _Geometry,
        *,
        maximized: bool = False,
        full_screen: bool = False,
    ) -> None:
        """Store geometry and display-state values."""

        self._geometry = geometry
        self._maximized = maximized
        self._full_screen = full_screen
        self.geometry_calls: list[tuple[int, int, int, int]] = []
        self.display_calls: list[str] = []

    def geometry(self) -> _Geometry:
        """Return the stored geometry."""

        return self._geometry

    def isMaximized(self) -> bool:  # noqa: N802
        """Return whether the window is maximized."""

        return self._maximized

    def isFullScreen(self) -> bool:  # noqa: N802
        """Return whether the window is fullscreen."""

        return self._full_screen

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:  # noqa: N802
        """Record one geometry application."""

        self.geometry_calls.append((x, y, width, height))

    def showNormal(self) -> None:  # noqa: N802
        """Record a normal display-state request."""

        self.display_calls.append("normal")

    def showMaximized(self) -> None:  # noqa: N802
        """Record a maximized display-state request."""

        self.display_calls.append("maximized")

    def showFullScreen(self) -> None:  # noqa: N802
        """Record a fullscreen display-state request."""

        self.display_calls.append("fullscreen")


class _OverrideMenuController:
    """Record requests to close the workflow override popup."""

    def __init__(self) -> None:
        """Create an empty close recorder."""

        self.close_calls = 0

    def close_menu_if_open(self) -> None:
        """Record one close request."""

        self.close_calls += 1


class _OverrideManager:
    """Record workflow override toolbar clearing."""

    def __init__(self) -> None:
        """Create an empty clear recorder."""

        self.clear_calls = 0

    def clear_toolbar_override_controls(self) -> None:
        """Record one toolbar clear request."""

        self.clear_calls += 1


def _restored_layout_shell(
    *,
    splitter: _Splitter,
    stack_width: int,
) -> SimpleNamespace:
    """Build a shell fake with dependencies needed for restored layout tests."""

    return SimpleNamespace(
        _active_workspace_route="wf-a",
        _remembered_workflow_splitter_sizes=(),
        _restored_shell_layout_applied=False,
        _pending_restore_projection_cache_capture_workflow_id="",
        splitter=splitter,
        editor_output_splitter=_Splitter([100, 50]),
        cube_stack_container=_StackContainer(stack_width),
        cube_stacks={},
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        sidePanelHost=SimpleNamespace(
            set_panel_width=lambda _width: None,
            set_queue_panel_visible=lambda _visible: None,
        ),
        comfy_runtime_actions=SimpleNamespace(
            set_comfy_output_panel_visible=lambda _visible: None
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        restore_finalized=SimpleNamespace(emit=lambda: None),
        window=lambda: _Window(_Geometry(0, 0, 900, 600)),
    )


def test_route_chrome_methods_apply_live_widget_state() -> None:
    """Route chrome methods should mutate only the owned shell widgets."""

    material_surface = _MaterialSurface()
    cube_container = object()
    cube_mode_button = _Button()
    orb_cluster = _VisibilityWidget()
    settings_search = _VisibilityWidget()
    app_orb_menu = _AppOrbMenu()
    override_menu_controller = _OverrideMenuController()
    override_manager = _OverrideManager()
    shell = SimpleNamespace(
        workspace_body_material_surface=material_surface,
        cube_stack_container=cube_container,
        cubeStackModeButton=cube_mode_button,
        orbActionCluster=orb_cluster,
        settingsToolbarSearchBox=settings_search,
        appOrbMenuButton=app_orb_menu,
        active_override_manager=override_manager,
        override_dropdown_btn=SimpleNamespace(
            _menu_controller=override_menu_controller
        ),
    )

    controller = ShellLayoutController(shell)
    controller.set_cube_stack_material_region_enabled(True)
    controller.set_cube_stack_material_region_enabled(False)
    controller.set_cube_stack_mode_button_enabled(False)
    controller.set_orb_action_cluster_visible(False)
    controller.set_settings_toolbar_search_visible(True)
    controller.set_workflow_override_toolbar_visible(False)
    controller.set_app_orb_workflow_file_actions_enabled(False)

    assert material_surface.regions == [cube_container, None]
    assert cube_mode_button.enabled == [False]
    assert orb_cluster.visible == [False]
    assert override_menu_controller.close_calls == 1
    assert settings_search.visible == [True]
    assert override_manager.clear_calls == 1
    assert app_orb_menu.enabled == [False]


def test_settings_search_visibility_uses_show_hide_fallback() -> None:
    """Settings search visibility should support lightweight fallback widgets."""

    settings_search = _FallbackSearchWidget()
    controller = ShellLayoutController(
        SimpleNamespace(settingsToolbarSearchBox=settings_search)
    )

    controller.set_settings_toolbar_search_visible(True)
    controller.set_settings_toolbar_search_visible(False)

    assert settings_search.calls == ["show", "hide"]


def test_missing_optional_widgets_are_ignored() -> None:
    """Route chrome methods should tolerate shell doubles without all widgets."""

    controller = ShellLayoutController(SimpleNamespace())

    controller.set_cube_stack_material_region_enabled(True)
    controller.set_cube_stack_mode_button_enabled(True)
    controller.set_orb_action_cluster_visible(False)
    controller.set_settings_toolbar_search_visible(True)
    controller.set_app_orb_workflow_file_actions_enabled(True)


def test_main_splitter_move_remembers_workflow_sizes_before_autosave() -> None:
    """Workflow splitter movement should persist durable sizes before autosave."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _remembered_workflow_splitter_sizes=(),
        splitter=_Splitter([720, 280]),
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        request_session_autosave=lambda: calls.append("autosave"),
    )
    controller = ShellLayoutController(shell)

    controller.handle_main_splitter_moved(0, 1)

    assert shell._remembered_workflow_splitter_sizes == (720, 280)
    assert calls == ["position", "autosave"]


def test_toggle_canvas_tabs_show_and_hide_emit_correct_widths() -> None:
    """Canvas panel toggle should compute base and expanded widths consistently."""

    class _Emitter:
        """Record resize requests emitted by the shell."""

        def __init__(self) -> None:
            """Create an empty resize-request recorder."""

            self.calls: list[tuple[int, ...]] = []

        def emit(self, *args: int) -> None:
            """Record one signal emission."""

            self.calls.append(args)

    class _CanvasSplitter:
        """Record canvas tab insertion for toggle behavior."""

        def __init__(self, widgets: list[object]) -> None:
            """Create a splitter double with its current widget order."""

            self.widgets = list(widgets)
            self.insert_calls: list[tuple[int, object]] = []

        def indexOf(self, widget: object) -> int:  # noqa: N802
            """Return the index for one splitter widget."""

            try:
                return self.widgets.index(widget)
            except ValueError:
                return -1

        def insertWidget(self, index: int, widget: object) -> None:  # noqa: N802
            """Record and apply one widget insertion."""

            self.insert_calls.append((index, widget))
            self.widgets.insert(index, widget)

    class _Container:
        """Record reparenting when the canvas tabs are hidden."""

        def __init__(self) -> None:
            """Create an empty reparenting recorder."""

            self.parent_set: list[object | None] = []

        def setParent(self, parent: object | None) -> None:  # noqa: N802
            """Record one Qt-style parent mutation."""

            self.parent_set.append(parent)

    class _RecordingController(ShellLayoutController):
        """Record layout trace events while exercising controller behavior."""

        def __init__(
            self,
            shell: object,
            trace_calls: list[tuple[str, dict[str, object]]],
        ) -> None:
            """Store the shell and trace sink used by the test."""

            super().__init__(shell)
            self._trace_calls = trace_calls

        def log_editor_width_trace(self, event: str, **context: object) -> None:
            """Record one layout trace event."""

            self._trace_calls.append((event, context))

    emitted = _Emitter()
    canvas_container = _Container()
    editor_panel = SimpleNamespace(width=lambda: 320)
    cube_stack = SimpleNamespace(width=lambda: 180)
    trace_calls: list[tuple[str, dict[str, object]]] = []
    shell = SimpleNamespace(
        canvas_tabs=SimpleNamespace(
            sizeHint=lambda: SimpleNamespace(width=lambda: 260)
        ),
        editor_panel=editor_panel,
        cube_stack=cube_stack,
        canvas_tabs_container=canvas_container,
        splitter=_CanvasSplitter([editor_panel, cube_stack]),
        resize_requested=emitted,
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: trace_calls.append(("position", {}))
        ),
    )
    controller = _RecordingController(shell, trace_calls)

    controller.toggle_canvas_tabs(True)
    assert shell.splitter.insert_calls == [(1, canvas_container)]
    assert emitted.calls[-1] == (760,)

    controller.toggle_canvas_tabs(False)
    assert canvas_container.parent_set[-1] is None
    assert emitted.calls[-1] == (500,)
    assert [event for event, _context in trace_calls] == [
        "toggle canvas tabs requested",
        "toggle canvas tabs emitted show resize",
        "position",
        "toggle canvas tabs requested",
        "toggle canvas tabs emitted hide resize",
        "position",
    ]


def test_startup_default_splitter_layout_preserves_editor_width() -> None:
    """Startup default layout should size the left workspace from cube stack plus editor."""

    splitter = _Splitter([10, 10])
    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _remembered_workflow_splitter_sizes=(),
        _restored_shell_layout_applied=False,
        splitter=splitter,
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH),
        width=lambda: 1400,
    )
    controller = ShellLayoutController(shell)

    controller.apply_startup_default_splitter_layout()

    expected_details_width = CUBE_STACK_EXPANDED_WIDTH + 832
    assert splitter.sizes() == [expected_details_width, 1400 - expected_details_width]
    assert shell._remembered_workflow_splitter_sizes == (
        expected_details_width,
        1400 - expected_details_width,
    )


def test_restored_compact_mode_applies_to_existing_and_future_stacks() -> None:
    """Restored compact mode should update shell state, stacks, material, and button."""

    material_opacity: list[float] = []
    existing_stack = _RecordingCubeStack()
    future_stack = _RecordingCubeStack()
    mode_button = _ModeButton()
    shell = SimpleNamespace(
        cube_stack_container=_StackContainer(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={"wf-a": existing_stack},
        cubeStackModeButton=mode_button,
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_wash_opacity=lambda value: material_opacity.append(value)
        ),
    )
    controller = ShellLayoutController(shell)

    controller.apply_restored_cube_stack_compact(True)
    controller.apply_current_cube_stack_mode_to_stack(future_stack)

    assert shell._cube_stack_compact is True
    assert existing_stack.compact_values == [True]
    assert future_stack.compact_values == [True]
    assert shell.cube_stack_container.width() == CUBE_STACK_COMPACT_WIDTH
    assert material_opacity == [0.0]
    assert mode_button.checked_values == [(True, True)]
    assert mode_button.tooltips == ["Expand cube stack"]


def test_compact_toggle_without_transition_transfers_width_to_canvas() -> None:
    """Non-animated compact toggles should preserve editor width through the splitter."""

    details = object()
    canvas = object()
    splitter = _IndexedSplitter(
        [details, canvas],
        [CUBE_STACK_EXPANDED_WIDTH + 832, 500],
    )
    material_opacity: list[float] = []
    calls: list[str] = []
    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _cube_stack_mode_transition=None,
        _remembered_workflow_splitter_sizes=(),
        cube_stack_container=_StackContainer(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        editor_output_container=details,
        canvas_tabs_container=canvas,
        splitter=splitter,
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_wash_opacity=lambda value: material_opacity.append(value)
        ),
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        request_session_autosave=lambda: calls.append("autosave"),
    )
    controller = ShellLayoutController(shell)

    controller.set_cube_stack_compact(True)

    freed_width = CUBE_STACK_EXPANDED_WIDTH - CUBE_STACK_COMPACT_WIDTH
    assert shell._remembered_workflow_splitter_sizes == (
        CUBE_STACK_EXPANDED_WIDTH + 832 - freed_width,
        500 + freed_width,
    )
    assert shell._cube_stack_compact is True
    assert splitter.sizes() == [
        CUBE_STACK_EXPANDED_WIDTH + 832 - freed_width,
        500 + freed_width,
    ]
    assert shell.cube_stack_container.width() == CUBE_STACK_COMPACT_WIDTH
    assert material_opacity == [0.0]
    assert calls == ["position", "autosave"]


def test_generation_queue_panel_visibility_uses_target_state_before_host() -> None:
    """Queue panel visibility should prefer shell target state over live host state."""

    shell = SimpleNamespace(
        _generation_queue_panel_visible=False,
        sidePanelHost=SimpleNamespace(is_queue_panel_visible=lambda: True),
    )
    controller = ShellLayoutController(shell)

    assert controller.current_generation_queue_panel_visible() is False

    controller.set_generation_queue_panel_visible_state(True)

    assert controller.current_generation_queue_panel_visible() is True
    assert shell._generation_queue_panel_visible is True


def test_generation_queue_panel_visibility_falls_back_to_host() -> None:
    """Queue panel visibility should read the host before target state exists."""

    shell = SimpleNamespace(
        sidePanelHost=SimpleNamespace(is_queue_panel_visible=lambda: True)
    )
    controller = ShellLayoutController(shell)

    assert controller.current_generation_queue_panel_visible() is True


def test_shell_layout_snapshot_captures_canonical_dimensions() -> None:
    """Snapshot capture should persist canonical dimensions from live shell widgets."""

    canvas_layout = CanvasLayoutSnapshot(
        floating_windows=(
            FloatingCanvasWindowSnapshot(
                label="Output",
                output_generation_controls_revealed=True,
            ),
        )
    )
    shell = SimpleNamespace(
        window=lambda: _Window(
            _Geometry(10, 20, 1200, 800),
            maximized=True,
        ),
        _active_workspace_route="wf-a",
        _cube_stack_compact=False,
        _generation_queue_panel_visible=True,
        _remembered_workflow_splitter_sizes=(
            CUBE_STACK_EXPANDED_WIDTH + 832,
            500,
            360,
        ),
        splitter=_Splitter([CUBE_STACK_EXPANDED_WIDTH + 832, 500, 360]),
        editor_output_splitter=_Splitter([700, 300]),
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH),
        canvas_tabs_container=SimpleNamespace(width=lambda: 500),
        active_editor_panel=SimpleNamespace(width=lambda: 832),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        comfy_output_panel=SimpleNamespace(height=lambda: 240),
        comfy_runtime_actions=SimpleNamespace(
            is_comfy_output_panel_visible=lambda: True
        ),
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: False,
            panel_width=lambda: 360,
        ),
        canvas_tabs=SimpleNamespace(canvas_layout_snapshot=lambda: canvas_layout),
    )
    controller = ShellLayoutController(shell)

    snapshot = controller.capture_shell_layout_snapshot()

    assert snapshot is not None
    assert snapshot.geometry is not None
    assert snapshot.geometry.x == 10
    assert snapshot.geometry.y == 20
    assert snapshot.geometry.width == 1200
    assert snapshot.geometry.height == 800
    assert snapshot.window_display_state == "maximized"
    assert snapshot.maximized is True
    assert snapshot.main_splitter_sizes == (CUBE_STACK_EXPANDED_WIDTH + 832, 500, 360)
    assert snapshot.editor_output_splitter_sizes == (700, 300)
    assert snapshot.cube_stack_width == CUBE_STACK_EXPANDED_WIDTH
    assert snapshot.editor_panel_width == 832
    assert snapshot.canvas_panel_width == 500
    assert snapshot.comfy_output_panel_visible is True
    assert snapshot.output_panel_height == 240
    assert snapshot.side_panel_visible is True
    assert snapshot.side_panel_width == 360
    assert snapshot.generation_queue_panel_visible is True
    assert snapshot.generation_queue_panel_width == 360
    assert snapshot.canvas_layout is canvas_layout


def test_shell_layout_snapshot_preserves_workflow_splitters_from_settings() -> None:
    """Settings route capture should retain the workflow splitter layout underneath."""

    shell = SimpleNamespace(
        window=lambda: _Window(_Geometry(1, 2, 1200, 800)),
        _active_workspace_route=SETTINGS_WORKSPACE_ROUTE,
        _cube_stack_compact=True,
        _remembered_workflow_splitter_sizes=(),
        splitter=_Splitter([640, 360]),
        editor_output_splitter=_Splitter([700, 300]),
        cube_stack_container=SimpleNamespace(width=lambda: 58),
        comfy_runtime_actions=SimpleNamespace(
            is_comfy_output_panel_visible=lambda: False
        ),
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: False,
            panel_width=lambda: 360,
        ),
    )
    controller = ShellLayoutController(shell)

    snapshot = controller.capture_shell_layout_snapshot()

    assert snapshot is not None
    assert snapshot.main_splitter_sizes == (640, 360)
    assert snapshot.cube_stack_width == CUBE_STACK_COMPACT_WIDTH
    assert snapshot.editor_panel_width == 640 - CUBE_STACK_COMPACT_WIDTH
    assert snapshot.canvas_panel_width == 360
    assert snapshot.cube_stack_compact is True


def test_shell_layout_snapshot_prefers_remembered_workflow_splitter_for_reload() -> (
    None
):
    """GUI reload capture should use durable workflow width over Settings width."""

    shell = SimpleNamespace(
        window=lambda: _Window(_Geometry(1, 2, 1200, 800)),
        _active_workspace_route=SETTINGS_WORKSPACE_ROUTE,
        _cube_stack_compact=False,
        _remembered_workflow_splitter_sizes=(720, 280),
        splitter=_Splitter([1000, 0]),
        editor_output_splitter=_Splitter([700, 300]),
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        comfy_runtime_actions=SimpleNamespace(
            is_comfy_output_panel_visible=lambda: False
        ),
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: False,
            panel_width=lambda: 360,
        ),
    )
    controller = ShellLayoutController(shell)

    snapshot = controller.capture_shell_layout_snapshot()

    assert snapshot is not None
    assert snapshot.main_splitter_sizes == (720, 280)
    assert snapshot.cube_stack_width == CUBE_STACK_EXPANDED_WIDTH
    assert snapshot.editor_panel_width == 720 - CUBE_STACK_EXPANDED_WIDTH
    assert snapshot.canvas_panel_width == 280


def test_shell_layout_snapshot_derives_stack_width_from_mode() -> None:
    """Snapshot capture should persist canonical stack width for the active mode."""

    common = {
        "window": lambda: _Window(_Geometry(1, 2, 1200, 800)),
        "_active_workspace_route": "wf-a",
        "_remembered_workflow_splitter_sizes": (
            CUBE_STACK_EXPANDED_WIDTH + 832,
            500,
            0,
        ),
        "splitter": _Splitter([CUBE_STACK_EXPANDED_WIDTH + 832, 500, 0]),
        "editor_output_splitter": _Splitter([700, 300]),
        "canvas_tabs_container": SimpleNamespace(width=lambda: 500),
        "active_editor_panel": SimpleNamespace(width=lambda: 832),
        "workflow_session_service": SimpleNamespace(active_workflow_id="wf-a"),
        "comfy_runtime_actions": SimpleNamespace(
            is_comfy_output_panel_visible=lambda: False
        ),
        "sidePanelHost": SimpleNamespace(
            is_queue_panel_visible=lambda: False,
            panel_width=lambda: 360,
        ),
    }
    compact_shell = SimpleNamespace(
        **common,
        _cube_stack_compact=True,
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH),
    )
    expanded_shell = SimpleNamespace(
        **common,
        _cube_stack_compact=False,
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_COMPACT_WIDTH),
    )

    compact_snapshot = ShellLayoutController(
        compact_shell
    ).capture_shell_layout_snapshot()
    expanded_snapshot = ShellLayoutController(
        expanded_shell
    ).capture_shell_layout_snapshot()

    assert compact_snapshot is not None
    assert compact_snapshot.cube_stack_width == CUBE_STACK_COMPACT_WIDTH
    assert expanded_snapshot is not None
    assert expanded_snapshot.cube_stack_width == CUBE_STACK_EXPANDED_WIDTH


def test_shell_layout_snapshot_widths_fall_back_to_splitter_and_canvas() -> None:
    """Snapshot width helpers should tolerate unavailable live editor widgets."""

    shell = SimpleNamespace(
        window=lambda: _Window(_Geometry(0, 0, 900, 600)),
        _active_workspace_route="wf-a",
        _cube_stack_compact=True,
        _remembered_workflow_splitter_sizes=(),
        splitter=_Splitter([700]),
        editor_output_splitter=_Splitter([600, 200]),
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH),
        canvas_tabs_container=SimpleNamespace(width=lambda: 420),
        active_editor_panel=SimpleNamespace(
            width=lambda: (_ for _ in ()).throw(RuntimeError)
        ),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        comfy_runtime_actions=SimpleNamespace(
            is_comfy_output_panel_visible=lambda: False
        ),
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: False,
            panel_width=lambda: 360,
        ),
    )
    controller = ShellLayoutController(shell)

    snapshot = controller.capture_shell_layout_snapshot()

    assert snapshot is not None
    assert snapshot.cube_stack_width == CUBE_STACK_COMPACT_WIDTH
    assert snapshot.editor_panel_width == 700 - CUBE_STACK_COMPACT_WIDTH
    assert snapshot.canvas_panel_width == 420


def test_apply_restored_shell_layout_applies_plan_and_finalizes() -> None:
    """Restored layout application should update live shell widgets and finalize."""

    window = _Window(_Geometry(0, 0, 900, 600))
    side_panel_widths: list[int] = []
    side_panel_visibility: list[bool] = []
    output_visibility: list[bool] = []
    generation_availability_calls: list[str] = []
    restore_finalized_calls: list[str] = []
    canvas_layout = CanvasLayoutSnapshot(
        floating_windows=(FloatingCanvasWindowSnapshot(label="Input"),)
    )
    canvas_layout_calls: list[CanvasLayoutSnapshot | None] = []
    splitter = _Splitter([900, 700, 0])
    editor_output_splitter = _Splitter([600, 200])
    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _remembered_workflow_splitter_sizes=(),
        _restored_shell_layout_applied=False,
        _pending_restore_projection_cache_capture_workflow_id="wf-a",
        splitter=splitter,
        editor_output_splitter=editor_output_splitter,
        cube_stack_container=_StackContainer(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        sidePanelHost=SimpleNamespace(
            set_panel_width=side_panel_widths.append,
            set_queue_panel_visible=side_panel_visibility.append,
        ),
        comfy_runtime_actions=SimpleNamespace(
            set_comfy_output_panel_visible=output_visibility.append
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: (
                generation_availability_calls.append("availability")
            )
        ),
        restore_finalized=SimpleNamespace(
            emit=lambda: restore_finalized_calls.append("finalized")
        ),
        canvas_tabs=SimpleNamespace(
            apply_restored_canvas_layout=canvas_layout_calls.append
        ),
        window=lambda: window,
    )
    controller = ShellLayoutController(shell)

    controller.apply_restored_shell_layout(
        ShellLayoutSnapshot(
            geometry=WindowGeometrySnapshot(x=10, y=20, width=1200, height=800),
            maximized=True,
            cube_stack_width=CUBE_STACK_EXPANDED_WIDTH,
            editor_panel_width=832,
            canvas_panel_width=500,
            side_panel_visible=True,
            side_panel_width=360,
            generation_queue_panel_visible=True,
            comfy_output_panel_visible=True,
            editor_output_splitter_sizes=(700, 300),
            canvas_layout=canvas_layout,
        )
    )

    assert shell._restored_shell_layout_applied is True
    assert shell._shell_restore_lifecycle == "running"
    assert shell._pending_restored_shell_layout is None
    assert window.geometry_calls == [(10, 20, 1200, 800)]
    assert window.display_calls == ["maximized"]
    expected_details_width = CUBE_STACK_EXPANDED_WIDTH + 832
    assert splitter.sizes() == [
        expected_details_width,
        1600 - expected_details_width - 360,
        360,
    ]
    assert editor_output_splitter.sizes() == [700, 300]
    assert shell._remembered_workflow_splitter_sizes == (
        expected_details_width,
        1600 - expected_details_width - 360,
        360,
    )
    assert shell.cube_stack_container.width() == CUBE_STACK_EXPANDED_WIDTH
    assert side_panel_widths == [360]
    assert side_panel_visibility == [True]
    assert output_visibility == [True]
    assert generation_availability_calls == ["availability"]
    assert restore_finalized_calls == ["finalized"]
    assert shell._pending_restore_projection_cache_capture_workflow_id == ""
    assert canvas_layout_calls == [canvas_layout]


def test_restored_shell_layout_blocks_startup_default_splitter_layout() -> None:
    """Startup default sizing must not overwrite restored workflow splitter sizes."""

    splitter = _Splitter([10, 10])
    editor_output_splitter = _Splitter([100, 50])
    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _remembered_workflow_splitter_sizes=(),
        _restored_shell_layout_applied=False,
        splitter=splitter,
        editor_output_splitter=editor_output_splitter,
        cube_stack_container=_StackContainer(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        sidePanelHost=SimpleNamespace(
            set_panel_width=lambda _width: None,
            set_queue_panel_visible=lambda _visible: None,
        ),
        comfy_runtime_actions=SimpleNamespace(
            set_comfy_output_panel_visible=lambda _visible: None
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        restore_finalized=SimpleNamespace(emit=lambda: None),
        _pending_restore_projection_cache_capture_workflow_id="",
        window=lambda: _Window(_Geometry(0, 0, 900, 600)),
        width=lambda: 1600,
    )
    controller = ShellLayoutController(shell)

    controller.apply_restored_shell_layout(
        ShellLayoutSnapshot(
            main_splitter_sizes=(640, 360),
            editor_output_splitter_sizes=(700, 300),
        ),
    )
    controller.apply_startup_default_splitter_layout()

    assert splitter.sizes() == [640, 360]
    assert editor_output_splitter.sizes() == [700, 300]
    assert shell._remembered_workflow_splitter_sizes == (640, 360)


def test_restored_stack_mode_repairs_serialized_width() -> None:
    """Restored compactness should repair stack width without double transfer."""

    compact_splitter = _Splitter([10, 10])
    compact_shell = _restored_layout_shell(
        splitter=compact_splitter,
        stack_width=CUBE_STACK_EXPANDED_WIDTH,
    )
    expanded_splitter = _Splitter([10, 10])
    expanded_shell = _restored_layout_shell(
        splitter=expanded_splitter,
        stack_width=CUBE_STACK_COMPACT_WIDTH,
    )

    ShellLayoutController(compact_shell).apply_restored_shell_layout(
        ShellLayoutSnapshot(
            main_splitter_sizes=(520, 480),
            cube_stack_compact=True,
            cube_stack_width=CUBE_STACK_EXPANDED_WIDTH,
        ),
    )
    ShellLayoutController(expanded_shell).apply_restored_shell_layout(
        ShellLayoutSnapshot(
            main_splitter_sizes=(520, 480),
            cube_stack_compact=False,
            cube_stack_width=CUBE_STACK_COMPACT_WIDTH,
        ),
    )

    assert compact_splitter.sizes() == [520, 480]
    assert compact_shell.cube_stack_container.width() == CUBE_STACK_COMPACT_WIDTH
    assert expanded_splitter.sizes() == [520, 480]
    assert expanded_shell.cube_stack_container.width() == CUBE_STACK_EXPANDED_WIDTH


def test_deferred_shell_layout_restores_canvas_layout_only_on_finalize() -> None:
    """Floating canvas layout should restore after deferred shell layout finalizes."""

    canvas_layout = CanvasLayoutSnapshot(
        floating_windows=(FloatingCanvasWindowSnapshot(label="Input"),)
    )
    snapshot = ShellLayoutSnapshot(
        main_splitter_sizes=(520, 480),
        canvas_layout=canvas_layout,
    )
    canvas_restore_calls: list[object | None] = []
    finalized: list[str] = []
    shell = _restored_layout_shell(
        splitter=_Splitter([10, 10]),
        stack_width=CUBE_STACK_EXPANDED_WIDTH,
    )
    shell._pending_restored_shell_layout = snapshot
    shell.canvas_tabs = SimpleNamespace(
        apply_restored_canvas_layout=canvas_restore_calls.append
    )
    shell.restore_finalized = SimpleNamespace(emit=lambda: finalized.append("done"))
    controller = ShellLayoutController(shell)

    controller.apply_deferred_restored_shell_layout(snapshot, finalize=False)
    controller.apply_deferred_restored_shell_layout(snapshot, finalize=True)

    assert canvas_restore_calls == [canvas_layout]
    assert finalized == ["done"]
    assert shell._shell_restore_lifecycle == "running"


def test_apply_restored_shell_layout_without_snapshot_finishes_restore_lifecycle() -> (
    None
):
    """Missing layout snapshots should still finish restore lifecycle startup state."""

    shell = SimpleNamespace(
        _active_workspace_route="wf-a",
        _shell_restore_lifecycle="restoring",
        _pending_restore_projection_cache_capture_workflow_id="wf-a",
    )
    controller = ShellLayoutController(shell)

    controller.apply_restored_shell_layout(None)

    assert shell._shell_restore_lifecycle == "running"
    assert shell._pending_restore_projection_cache_capture_workflow_id == ""
