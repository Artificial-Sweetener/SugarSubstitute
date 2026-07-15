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

"""Cover shell geometry and cube-stack transition behavior outside MainWindow."""

from __future__ import annotations

import types
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

import substitute.presentation.shell.session_autosave_controller as session_autosave_controller_module
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.canvas_route_controller import CanvasRouteController
from substitute.presentation.shell.comfy_runtime_actions import ComfyRuntimeActions
from substitute.presentation.shell.cube_stack_mode_transition import (
    CubeStackModeTransition,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.presentation.shell.shell_layout_controller import ShellLayoutController
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)


class _Signal:
    """Capture Qt-like signal connections and allow test-time emission."""

    def __init__(self) -> None:
        """Initialize an empty connection list."""

        self.connections: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Record connected callbacks."""

        self.connections.append(callback)

    def fire(self, *args: object) -> None:
        """Invoke all connected callbacks with one emitted payload."""

        for callback in self.connections:
            callback(*args)


class _AnimationStub:
    """Small QPropertyAnimation test double for geometry-only contracts."""

    def __init__(self, *_args: object) -> None:
        """Initialize a deterministic finished signal."""

        self.finished = _Signal()
        self.started = False

    def stop(self) -> None:
        """Accept stop calls without touching Qt animation internals."""

    def setStartValue(self, _value: object) -> None:  # noqa: N802
        """Accept start-value updates."""

    def setEndValue(self, _value: object) -> None:  # noqa: N802
        """Accept end-value updates."""

    def setDuration(self, _duration: int) -> None:  # noqa: N802
        """Accept duration updates."""

    def setEasingCurve(self, _curve: object) -> None:  # noqa: N802
        """Accept easing-curve updates."""

    def start(self) -> None:
        """Record that an animation would have started."""

        self.started = True


def _install_cube_stack_animation_stub(
    monkeypatch: pytest.MonkeyPatch,
    transition_type: Any,
) -> None:
    """Use a deterministic animation double for cube-stack geometry contracts."""

    monkeypatch.setitem(
        transition_type.__init__.__globals__,
        "QPropertyAnimation",
        _AnimationStub,
    )


def _replace_transition_finish_signal(
    monkeypatch: pytest.MonkeyPatch,
    transition: Any,
) -> None:
    """Keep transition finish side effects while avoiding direct Qt signal emit."""

    def finish_without_qt_signal(transition_self: Any) -> None:
        transition_self._animating = False
        target_progress = 1.0 if transition_self._target_compact else 0.0
        transition_self._progress = target_progress
        stack_width = (
            CUBE_STACK_COMPACT_WIDTH
            if transition_self._target_compact
            else CUBE_STACK_EXPANDED_WIDTH
        )
        item_width = round(
            CubeStackModeTransition._item_width_for_progress(target_progress)
        )
        transition_self._set_container_width(stack_width)
        transition_self._apply_stack_progress(stack_width, item_width, target_progress)
        transition_self._apply_splitter_progress(stack_width)
        transition_self._apply_material_progress()
        transition_self._finish_stack_transitions(transition_self._target_compact)
        transition_self._position_search_box()

    monkeypatch.setattr(
        transition,
        "_finish_transition",
        types.MethodType(finish_without_qt_signal, transition),
    )


class _LayoutSplitter:
    """Expose minimal splitter sizing behavior for shell-layout tests."""

    def __init__(self, sizes: list[int]) -> None:
        """Store initial splitter sizes."""

        self._sizes = list(sizes)

    def sizes(self) -> list[int]:
        """Return current splitter sizes."""

        return list(self._sizes)

    def setSizes(self, sizes: list[int]) -> None:  # noqa: N802
        """Store new splitter sizes."""

        self._sizes = list(sizes)


class _IndexedLayoutSplitter(_LayoutSplitter):
    """Expose splitter index lookup as well as sizing."""

    def __init__(self, widgets: list[object], sizes: list[int]) -> None:
        """Store widgets and initial sizes."""

        super().__init__(sizes)
        self._widgets = list(widgets)

    def indexOf(self, widget: object) -> int:  # noqa: N802
        """Return the index for one widget or -1 when absent."""

        try:
            return self._widgets.index(widget)
        except ValueError:
            return -1


class _WidthSurface:
    """Expose fixed-width widget behavior for layout tests."""

    def __init__(self, width: int) -> None:
        """Store initial width."""

        self._width = width

    def width(self) -> int:
        """Return the current width."""

        return self._width

    def setFixedWidth(self, width: int) -> None:  # noqa: N802
        """Store the requested fixed width."""

        self._width = width


class _MaterialSurface:
    """Record cube-stack wash opacity updates for shell material tests."""

    def __init__(self) -> None:
        """Initialize opacity history."""

        self.opacity_values: list[float] = []

    def set_cube_stack_wash_opacity(self, value: float) -> None:
        """Record one cube-stack wash opacity update."""

        self.opacity_values.append(value)


class _RecordingCubeStack:
    """Record compact mode applied to one cube stack double."""

    def __init__(self) -> None:
        """Initialize compact mode call history."""

        self.compact_values: list[bool] = []

    def setCompact(self, compact: bool) -> None:  # noqa: N802
        """Record one compact mode application."""

        self.compact_values.append(compact)

    def isCompact(self) -> bool:  # noqa: N802
        """Return the latest recorded compact mode."""

        return self.compact_values[-1] if self.compact_values else False


def _attach_shell_layout_controller(fake: SimpleNamespace) -> SimpleNamespace:
    """Attach composed shell controllers expected by layout methods."""

    fake.shell_layout_controller = ShellLayoutController(fake)
    if not hasattr(fake, "generation_action_controller"):
        fake.generation_action_controller = GenerationActionController(fake)
    if not hasattr(fake, "active_workflow_surface_refresher"):
        fake.active_workflow_surface_refresher = ActiveWorkflowSurfaceRefresher(fake)
    if not hasattr(fake, "comfy_runtime_actions"):
        fake.comfy_runtime_actions = ComfyRuntimeActions(fake)
    if not hasattr(fake, "canvas_route_controller"):
        fake.canvas_route_controller = CanvasRouteController(fake)
    return fake


def test_cube_stack_compact_updates_durable_workflow_splitter_width() -> None:
    """Cube-stack width transfer should update the snapshot splitter source."""

    details = object()
    canvas = object()
    splitter = _IndexedLayoutSplitter(
        [details, canvas],
        [CUBE_STACK_EXPANDED_WIDTH + 832, 500],
    )
    fake = SimpleNamespace(
        _active_workspace_route="wf-a",
        _cube_stack_mode_transition=None,
        _remembered_workflow_splitter_sizes=(),
        cube_stack_container=_WidthSurface(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        editor_output_container=details,
        canvas_tabs_container=canvas,
        splitter=splitter,
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        workspace_body_material_surface=_MaterialSurface(),
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
        request_session_autosave=lambda: None,
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.set_cube_stack_compact(True)

    freed_width = CUBE_STACK_EXPANDED_WIDTH - CUBE_STACK_COMPACT_WIDTH
    assert fake._remembered_workflow_splitter_sizes == (
        CUBE_STACK_EXPANDED_WIDTH + 832 - freed_width,
        500 + freed_width,
    )
    assert fake._cube_stack_compact is True
    assert fake.workspace_body_material_surface.opacity_values == [0.0]


def test_restored_compact_mode_applies_to_later_deferred_stack() -> None:
    """Deferred restored workflow stacks should inherit restored compact mode."""

    existing_stack = _RecordingCubeStack()
    future_stack = _RecordingCubeStack()
    fake = SimpleNamespace(
        _active_workspace_route="wf-a",
        cube_stack_container=_WidthSurface(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={"wf-active": existing_stack},
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        workspace_body_material_surface=_MaterialSurface(),
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.apply_restored_cube_stack_compact(True)
    fake.shell_layout_controller.apply_current_cube_stack_mode_to_stack(future_stack)

    assert fake._cube_stack_compact is True
    assert existing_stack.compact_values == [True]
    assert future_stack.compact_values == [True]
    assert fake.cube_stack_container.width() == CUBE_STACK_COMPACT_WIDTH
    assert fake.workspace_body_material_surface.opacity_values == [0.0]


def test_restored_compact_mode_syncs_toolbar_button_checked_state() -> None:
    """Restored compact mode should not require a catch-up toolbar click."""

    class _Button:
        def __init__(self) -> None:
            self.blocked = False
            self.checked_values: list[tuple[bool, bool]] = []
            self.emitted_values: list[bool] = []
            self.icons: list[Any] = []
            self.tooltips: list[str] = []

        def blockSignals(self, blocked: bool) -> bool:  # noqa: N802
            previous = self.blocked
            self.blocked = blocked
            return previous

        def setChecked(self, checked: bool) -> None:  # noqa: N802
            self.checked_values.append((checked, self.blocked))
            if not self.blocked:
                self.emitted_values.append(checked)

        def setIcon(self, icon: object) -> None:  # noqa: N802
            self.icons.append(icon)

        def setToolTip(self, tooltip: str) -> None:  # noqa: N802
            self.tooltips.append(tooltip)

    button = _Button()
    fake = SimpleNamespace(
        _active_workspace_route="wf-a",
        cube_stack_container=_WidthSurface(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        cubeStackModeButton=button,
        workspace_body_material_surface=_MaterialSurface(),
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.apply_restored_cube_stack_compact(True)

    assert button.checked_values == [(True, True)]
    assert button.emitted_values == []
    assert button.blocked is False
    assert button.icons[-1].value == AppIcon.PANEL_LEFT_20_REGULAR.value
    assert button.tooltips[-1] == "Expand cube stack"
    assert fake.workspace_body_material_surface.opacity_values == [0.0]


def test_restored_expanded_mode_applies_to_later_deferred_stack() -> None:
    """Deferred restored workflow stacks should inherit restored expanded mode."""

    existing_stack = _RecordingCubeStack()
    future_stack = _RecordingCubeStack()
    fake = SimpleNamespace(
        _active_workspace_route="wf-a",
        cube_stack_container=_WidthSurface(CUBE_STACK_COMPACT_WIDTH),
        cube_stacks={"wf-active": existing_stack},
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        workspace_body_material_surface=_MaterialSurface(),
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.apply_restored_cube_stack_compact(False)
    fake.shell_layout_controller.apply_current_cube_stack_mode_to_stack(future_stack)

    assert fake._cube_stack_compact is False
    assert existing_stack.compact_values == [False]
    assert future_stack.compact_values == [False]
    assert fake.cube_stack_container.width() == CUBE_STACK_EXPANDED_WIDTH
    assert fake.workspace_body_material_surface.opacity_values == [1.0]


def test_initial_left_workspace_width_preserves_editor_two_column_budget() -> None:
    """Initial left workspace sizing should include the cube stack width plus editor width."""

    fake = SimpleNamespace(
        cube_stack_container=SimpleNamespace(width=lambda: CUBE_STACK_EXPANDED_WIDTH)
    )

    assert (
        ShellLayoutController(fake).initial_left_workspace_width()
        == CUBE_STACK_EXPANDED_WIDTH + 832
    )


def test_set_cube_stack_compact_delegates_workflow_route_to_transition() -> None:
    """Workflow cube-stack mode changes should use the shell transition driver."""

    class _Button:
        def __init__(self) -> None:
            self.tooltips: list[str] = []
            self.icons: list[Any] = []

        def setToolTip(self, tooltip: str) -> None:  # noqa: N802
            self.tooltips.append(tooltip)

        def setIcon(self, icon: object) -> None:  # noqa: N802
            self.icons.append(icon)

    transition_calls: list[bool] = []
    button = _Button()
    fake = SimpleNamespace(
        _active_workspace_route="workflow-a",
        _cube_stack_mode_transition=SimpleNamespace(
            transition_to=lambda compact: transition_calls.append(compact)
        ),
        cubeStackModeButton=button,
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.set_cube_stack_compact(True)

    assert transition_calls == [True]
    assert fake._cube_stack_compact is True
    assert button.icons[-1].value == AppIcon.PANEL_LEFT_20_REGULAR.value
    assert button.tooltips[-1] == "Expand cube stack"
    future_stack = _RecordingCubeStack()
    fake.shell_layout_controller.apply_current_cube_stack_mode_to_stack(future_stack)
    assert future_stack.compact_values == [True]

    fake.shell_layout_controller.set_cube_stack_compact(False)

    assert transition_calls == [True, False]
    assert fake._cube_stack_compact is False
    assert button.icons[-1].value == AppIcon.PANEL_LEFT_20_FILLED.value
    assert button.tooltips[-1] == "Collapse cube stack"


def test_set_cube_stack_compact_on_complete_waits_for_matching_transition() -> None:
    """Compact toggle completion should run only for the requested transition target."""

    completion_calls: list[str] = []
    transition_calls: list[bool] = []
    transition_finished = _Signal()
    fake = SimpleNamespace(
        _active_workspace_route="workflow-a",
        _cube_stack_mode_transition=SimpleNamespace(
            transitionFinished=transition_finished,
            transition_to=lambda compact: transition_calls.append(compact),
        ),
        cubeStackModeButton=SimpleNamespace(setToolTip=lambda _tooltip: None),
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
    )
    fake = _attach_shell_layout_controller(fake)

    fake.shell_layout_controller.set_cube_stack_compact(
        False,
        on_complete=lambda: completion_calls.append("done"),
        manual=False,
    )

    assert transition_calls == [False]
    assert completion_calls == []

    transition_finished.fire(True)
    assert completion_calls == []

    transition_finished.fire(False)
    assert completion_calls == ["done"]


def test_cube_stack_mode_transition_transfers_width_without_delta_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transition progress should derive splitter sizes from captured start geometry."""

    _install_cube_stack_animation_stub(monkeypatch, CubeStackModeTransition)

    class _Container:
        def __init__(self, width: int) -> None:
            self._width = width
            self.fixed_widths: list[int] = []

        def width(self) -> int:
            return self._width

        def setFixedWidth(self, width: int) -> None:  # noqa: N802
            self.fixed_widths.append(width)
            self._width = width

    class _Splitter:
        def __init__(self, widgets: list[object], sizes: list[int]) -> None:
            self.widgets = list(widgets)
            self._sizes = list(sizes)
            self.set_size_calls: list[list[int]] = []

        def indexOf(self, widget: object) -> int:  # noqa: N802
            try:
                return self.widgets.index(widget)
            except ValueError:
                return -1

        def sizes(self) -> list[int]:
            return list(self._sizes)

        def setSizes(self, sizes: list[int]) -> None:  # noqa: N802
            self.set_size_calls.append(list(sizes))
            self._sizes = list(sizes)

    class _Stack:
        def __init__(self) -> None:
            self.begin_calls: list[bool] = []
            self.apply_calls: list[dict[str, object]] = []
            self.finish_calls: list[bool] = []

        def beginCompactTransition(self, target_compact: bool) -> None:  # noqa: N802
            self.begin_calls.append(target_compact)

        def applyCompactTransition(  # noqa: N802
            self,
            *,
            stack_width: int,
            item_width: int,
            compact_progress: float,
        ) -> None:
            self.apply_calls.append(
                {
                    "stack_width": stack_width,
                    "item_width": item_width,
                    "compact_progress": compact_progress,
                }
            )

        def finishCompactTransition(self, target_compact: bool) -> None:  # noqa: N802
            self.finish_calls.append(target_compact)

    details = object()
    canvas = object()
    stack = _Stack()
    material_progress: list[float] = []
    fake = SimpleNamespace(
        cube_stack_container=_Container(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={"wf-a": stack},
        editor_output_container=details,
        canvas_tabs_container=canvas,
        splitter=_Splitter(
            [details, canvas],
            [CUBE_STACK_EXPANDED_WIDTH + 832, 500],
        ),
        position_calls=[],
    )
    fake.search_overlay_controller = SimpleNamespace(
        position_search_box=lambda: fake.position_calls.append("position")
    )
    fake.shell_layout_controller = SimpleNamespace(
        remember_workflow_splitter_sizes=lambda _sizes: None,
        set_cube_stack_material_progress=lambda progress: material_progress.append(
            progress
        ),
        log_editor_width_trace=lambda *_args, **_kwargs: None,
    )
    transition = CubeStackModeTransition(fake)

    transition.transition_to(True)
    transition.setProgress(0.5)
    first_mid_sizes = fake.splitter.set_size_calls[-1]
    transition.setProgress(0.5)

    expected_width = round((CUBE_STACK_EXPANDED_WIDTH + CUBE_STACK_COMPACT_WIDTH) / 2)
    expected_item_width = round(CubeStackModeTransition._item_width_for_progress(0.5))
    freed_width = CUBE_STACK_EXPANDED_WIDTH - expected_width

    assert stack.begin_calls == [True]
    assert fake.cube_stack_container.fixed_widths[-1] == expected_width
    assert stack.apply_calls[-1] == {
        "stack_width": expected_width,
        "item_width": expected_item_width,
        "compact_progress": 0.5,
    }
    assert material_progress[-2:] == [0.5, 0.5]
    assert first_mid_sizes == [
        CUBE_STACK_EXPANDED_WIDTH + 832 - freed_width,
        500 + freed_width,
    ]
    assert fake.splitter.set_size_calls[-1] == first_mid_sizes
    transition.stop()


def test_cube_stack_mode_transition_tolerates_hidden_canvas_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transition should still resize stack surfaces when canvas is absent."""

    _install_cube_stack_animation_stub(monkeypatch, CubeStackModeTransition)

    class _Container:
        def __init__(self, width: int) -> None:
            self._width = width
            self.fixed_widths: list[int] = []

        def width(self) -> int:
            return self._width

        def setFixedWidth(self, width: int) -> None:  # noqa: N802
            self.fixed_widths.append(width)
            self._width = width

    class _Splitter:
        def __init__(self, widgets: list[object]) -> None:
            self.widgets = list(widgets)
            self.set_size_calls: list[list[int]] = []

        def indexOf(self, widget: object) -> int:  # noqa: N802
            try:
                return self.widgets.index(widget)
            except ValueError:
                return -1

        def sizes(self) -> list[int]:
            return [CUBE_STACK_EXPANDED_WIDTH + 832]

        def setSizes(self, sizes: list[int]) -> None:  # noqa: N802
            self.set_size_calls.append(list(sizes))

    details = object()
    canvas = object()
    material_progress: list[float] = []
    fake = SimpleNamespace(
        cube_stack_container=_Container(CUBE_STACK_EXPANDED_WIDTH),
        cube_stacks={},
        editor_output_container=details,
        canvas_tabs_container=canvas,
        splitter=_Splitter([details]),
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
    )
    fake.shell_layout_controller = SimpleNamespace(
        remember_workflow_splitter_sizes=lambda _sizes: None,
        set_cube_stack_material_progress=lambda progress: material_progress.append(
            progress
        ),
        log_editor_width_trace=lambda *_args, **_kwargs: None,
    )
    transition = CubeStackModeTransition(fake)

    transition.transition_to(True)
    transition.setProgress(1.0)

    assert fake.cube_stack_container.fixed_widths[-1] == CUBE_STACK_COMPACT_WIDTH
    assert fake.splitter.set_size_calls == []
    assert material_progress[-1] == 1.0
    transition.stop()


def test_cube_stack_mode_transition_reduced_motion_finishes_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reduced motion should commit the target mode without starting a transition."""

    _install_cube_stack_animation_stub(monkeypatch, CubeStackModeTransition)
    monkeypatch.setitem(
        CubeStackModeTransition.transition_to.__globals__,
        "resolve_motion_duration",
        lambda _duration: 0,
    )

    class _Container:
        def __init__(self) -> None:
            self.fixed_widths: list[int] = []

        def width(self) -> int:
            return CUBE_STACK_EXPANDED_WIDTH

        def setFixedWidth(self, width: int) -> None:  # noqa: N802
            self.fixed_widths.append(width)

    class _Stack:
        def __init__(self) -> None:
            self.begin_calls: list[bool] = []
            self.finish_calls: list[bool] = []

        def beginCompactTransition(self, target_compact: bool) -> None:  # noqa: N802
            self.begin_calls.append(target_compact)

        def applyCompactTransition(self, **_kwargs: object) -> None:  # noqa: N802
            pass

        def finishCompactTransition(self, target_compact: bool) -> None:  # noqa: N802
            self.finish_calls.append(target_compact)

    stack = _Stack()
    material_progress: list[float] = []
    fake = SimpleNamespace(
        cube_stack_container=_Container(),
        cube_stacks={"wf-a": stack},
        splitter=None,
        editor_output_container=None,
        canvas_tabs_container=None,
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
    )
    fake.shell_layout_controller = SimpleNamespace(
        remember_workflow_splitter_sizes=lambda _sizes: None,
        set_cube_stack_material_progress=lambda progress: material_progress.append(
            progress
        ),
        log_editor_width_trace=lambda *_args, **_kwargs: None,
    )
    transition = CubeStackModeTransition(fake)
    _replace_transition_finish_signal(monkeypatch, transition)

    transition.transition_to(True)

    assert transition.is_animating() is False
    assert fake.cube_stack_container.fixed_widths[-1] == CUBE_STACK_COMPACT_WIDTH
    assert stack.begin_calls == [True]
    assert stack.finish_calls == [True]
    assert material_progress[-1] == 1.0


def test_configure_resize_autosave_timer_uses_coordinator_timers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resize autosave setup should expose coordinator-owned single-shot timers."""

    created_timers: list[Any] = []

    class _Timeout:
        def __init__(self) -> None:
            self.callback: Callable[[], None] | None = None

        def connect(self, callback: Callable[[], None]) -> None:
            self.callback = callback

    class _Timer:
        def __init__(self, parent: object) -> None:
            self.parent = parent
            self.timeout = _Timeout()
            self.single_shot: bool | None = None
            created_timers.append(self)

        def setSingleShot(self, single_shot: bool) -> None:  # noqa: N802
            self.single_shot = single_shot

    fake = SimpleNamespace(request_session_autosave=lambda: None)
    monkeypatch.setattr(session_autosave_controller_module, "QTimer", _Timer)
    controller = session_autosave_controller_module.SessionAutosaveController(fake)

    controller.ensure_coordinator()

    categories = tuple(SessionAutosaveRequestCategory)
    resize_index = categories.index(SessionAutosaveRequestCategory.LAYOUT_RESIZE)
    assert len(created_timers) == len(SessionAutosaveRequestCategory)
    assert fake._tab_selection_autosave_timer is created_timers[0]
    assert fake._resize_autosave_timer is created_timers[resize_index]
    assert created_timers[0].parent is fake._session_autosave_coordinator
    assert created_timers[resize_index].parent is fake._session_autosave_coordinator
    assert all(timer.single_shot is True for timer in created_timers)
    assert all(timer.timeout.callback is not None for timer in created_timers)


def test_resize_autosave_timer_fires_session_autosave_once() -> None:
    """The resize autosave callback should reuse normal session autosave policy."""

    autosaves: list[str] = []
    fake = SimpleNamespace(
        _initial_workspace_hydrated=True,
        _shell_restore_lifecycle="running",
        session_autosave_service=SimpleNamespace(
            request_save=lambda _port: autosaves.append("save")
        ),
    )
    controller = session_autosave_controller_module.SessionAutosaveController(fake)

    controller.run_resize_autosave()

    assert autosaves == ["save"]
