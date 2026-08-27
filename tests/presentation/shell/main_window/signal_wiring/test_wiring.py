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

"""Verify MainWindow connects shell signals and schedules initial placement."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.shell import main_window_composition


class _Signal:
    """Record connected slots for one shell signal."""

    def __init__(self) -> None:
        """Initialize no connected slots."""

        self.connected: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self.connected.append(slot)


class _SignalBinder:
    """Record the composed binder connections."""

    def __init__(self, input_canvas: object, output_canvas: object) -> None:
        """Initialize deterministic canvas identity capture."""

        self.input_canvas = input_canvas
        self.output_canvas = output_canvas
        self.calls: list[str] = []

    def connect_generation_feedback_signals(self) -> None:
        """Record generation feedback binding."""

        self.calls.append("generation")

    def connect_search_signals(self) -> None:
        """Record search binding."""

        self.calls.append("search")

    def connect_menu_action_signals(self) -> None:
        """Record menu binding."""

        self.calls.append("menu")

    def connect_workflow_tab_signals(self) -> None:
        """Record workflow-tab binding."""

        self.calls.append("tabs")

    def connect_canvas_signals(
        self, *, input_canvas: object, output_canvas: object
    ) -> None:
        """Record canvas binding with concrete canvas identity."""

        self.calls.append(
            f"canvas:{input_canvas is self.input_canvas}:{output_canvas is self.output_canvas}"
        )


class _CanvasHost:
    """Expose the two required canvas routes and visibility signal."""

    def __init__(self, input_canvas: object, output_canvas: object) -> None:
        """Store the two canvas route values."""

        self.input_canvas = input_canvas
        self.output_canvas = output_canvas
        self.visibility_changed = _Signal()

    def canvas_for(self, route_key: str) -> object | None:
        """Return the canvas for the requested route."""

        return {"Input": self.input_canvas, "Output": self.output_canvas}.get(route_key)


class _LayoutController:
    """Provide layout signal endpoints and startup trace capture."""

    def __init__(self) -> None:
        """Initialize no trace messages."""

        self.trace_messages: list[str] = []

    def toggle_canvas_host(self) -> None:
        """Provide canvas-host visibility endpoint."""

    def handle_main_splitter_moved(self) -> None:
        """Provide main splitter endpoint."""

    def handle_editor_output_splitter_moved(self) -> None:
        """Provide editor-output splitter endpoint."""

    def apply_startup_default_splitter_layout(self) -> None:
        """Provide deferred splitter-layout endpoint."""

    def log_editor_width_trace(self, message: str) -> None:
        """Record the startup layout trace."""

        self.trace_messages.append(message)


class _CanvasRouteController:
    """Record canvas-route signal binding."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared binding log."""

        self.calls = calls

    def connect_canvas_route_signals(self) -> None:
        """Record canvas-route binding."""

        self.calls.append("connect")


class _AutosaveController:
    """Record canvas-layout autosave binding."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared binding log."""

        self.calls = calls

    def connect_canvas_layout_autosave(self) -> None:
        """Record canvas-layout autosave binding."""

        self.calls.append("canvas")


class _Splitter:
    """Expose one splitter-moved signal."""

    def __init__(self) -> None:
        """Create the splitter signal."""

        self.splitterMoved = _Signal()


class _EditorPanelContainer:
    """Expose the editor-panel selection signal."""

    def __init__(self) -> None:
        """Create the selection signal."""

        self.currentChanged = _Signal()


class _SearchOverlayController:
    """Provide the deferred search-box positioning endpoint."""

    def position_search_box(self) -> None:
        """Provide deferred search-box positioning."""


class _ProgressOverlayController:
    """Provide the deferred progress-overlay positioning endpoint."""

    def position_progress_overlay(self) -> None:
        """Provide deferred progress-overlay positioning."""


class _GenerationActionController:
    """Record generation-mode selection."""

    def __init__(self, modes: list[str]) -> None:
        """Store the selected-mode log."""

        self.modes = modes

    def set_generation_selected_mode(self, mode: str) -> None:
        """Record one selected generation mode."""

        self.modes.append(mode)


class _GenerationActionCluster:
    """Expose the generation mode-selection signal."""

    def __init__(self) -> None:
        """Create the mode-selection signal."""

        self.generateModeSelected = _Signal()


class _ComfyRuntimeActions:
    """Record Comfy output visibility changes."""

    def __init__(self, visibility: list[bool]) -> None:
        """Store the visibility log."""

        self.visibility = visibility

    def set_comfy_output_panel_visible(self, visible: bool) -> None:
        """Record one Comfy output visibility change."""

        self.visibility.append(visible)


class _Shell:
    """Hold local signal owners and their observable effects."""

    def __init__(self) -> None:
        """Create one complete signal-wiring shell contract."""

        self.input_canvas = object()
        self.output_canvas = object()
        self.main_window_signal_binder = _SignalBinder(
            self.input_canvas,
            self.output_canvas,
        )
        self.canvas_host = _CanvasHost(self.input_canvas, self.output_canvas)
        self.canvas_route_calls: list[str] = []
        self.canvas_route_controller = _CanvasRouteController(self.canvas_route_calls)
        self.workspace_layout_controller = _LayoutController()
        self.autosave_calls: list[str] = []
        self.session_autosave_controller = _AutosaveController(self.autosave_calls)
        self.splitter = _Splitter()
        self.editor_output_splitter = _Splitter()
        self.editor_panel_container = _EditorPanelContainer()
        self.search_overlay_controller = _SearchOverlayController()
        self.progress_overlay_controller = _ProgressOverlayController()
        self.generation_modes: list[str] = []
        self.generation_action_controller = _GenerationActionController(
            self.generation_modes
        )
        self.generationActionCluster = _GenerationActionCluster()
        self._generation_action_cluster_mode_callback: Callable[[str], None] | None = (
            None
        )
        self.comfy_visibility: list[bool] = []
        self.comfy_runtime_actions = _ComfyRuntimeActions(self.comfy_visibility)
        self.installed_filters: list[object] = []

    def installEventFilter(self, target: object) -> None:
        """Record the installed shell event filter."""

        self.installed_filters.append(target)


def test_connect_shell_signals_wires_controllers_and_startup_callbacks() -> None:
    """Bind shell interactions and defer first layout or overlay positioning."""

    shell = _Shell()
    scheduled: list[tuple[int, Callable[[], None]]] = []

    main_window_composition.connect_shell_signals(
        shell,
        startup_timer=None,
        single_shot=lambda delay, callback: scheduled.append((delay, callback)),
    )

    assert shell.main_window_signal_binder.calls == [
        "generation",
        "search",
        "menu",
        "tabs",
        "canvas:True:True",
    ]
    assert shell.canvas_route_calls == ["connect"]
    assert shell.autosave_calls == ["canvas"]
    assert shell.canvas_host.visibility_changed.connected == [
        shell.workspace_layout_controller.toggle_canvas_host
    ]
    assert shell.splitter.splitterMoved.connected == [
        shell.workspace_layout_controller.handle_main_splitter_moved
    ]
    assert shell.editor_output_splitter.splitterMoved.connected == [
        shell.workspace_layout_controller.handle_editor_output_splitter_moved
    ]
    assert len(shell.editor_panel_container.currentChanged.connected) == 1
    assert shell.generation_modes == ["generate"]
    assert shell.generationActionCluster.generateModeSelected.connected == [
        shell._generation_action_cluster_mode_callback
    ]
    assert shell.comfy_visibility == [False]
    assert shell.workspace_layout_controller.trace_messages == [
        "scheduling startup default splitter layout"
    ]
    assert scheduled == [
        (0, shell.workspace_layout_controller.apply_startup_default_splitter_layout),
        (0, shell.progress_overlay_controller.position_progress_overlay),
        (0, shell.search_overlay_controller.position_search_box),
    ]
    assert shell.installed_filters == [shell]
