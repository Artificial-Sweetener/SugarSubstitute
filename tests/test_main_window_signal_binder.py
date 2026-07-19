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

"""Tests for MainWindow signal binding ownership."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)

from substitute.presentation.shell import main_window_signal_binder as signal_binder_mod
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
    main_window_signal_binder_for,
)
from substitute.presentation.shell.cube_loader import load_cube_async
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)


class _Signal:
    """Capture Qt-like signal connections and allow deterministic emission."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.connections: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record a signal callback."""

        self.connections.append(callback)

    def fire(self, *args: object) -> None:
        """Invoke connected callbacks with the emitted payload."""

        for callback in self.connections:
            callback(*args)


class _AppOrbMenu:
    """Expose app-orb signals used by the signal binder."""

    def __init__(self) -> None:
        """Create every app-orb signal expected by the binder."""

        self.openRequested = _Signal()
        self.saveRequested = _Signal()
        self.saveAsRequested = _Signal()
        self.exportRequested = _Signal()
        self.settingsRequested = _Signal()
        self.comfyUiSettingsRequested = _Signal()
        self.restartGuiRequested = _Signal()
        self.restartComfyRequested = _Signal()


def test_signal_binder_for_reuses_composed_shell_instance() -> None:
    """Binder lookup should preserve the shell-composed owner."""

    shell = SimpleNamespace()
    binder = MainWindowSignalBinder(shell)
    shell.main_window_signal_binder = binder

    assert main_window_signal_binder_for(shell) is binder


def test_generation_feedback_signals_route_to_view_and_workspace_controller() -> None:
    """Generation feedback signals should bind to the existing presentation targets."""

    progress_calls: list[tuple[object, object]] = []
    preview_calls: list[object] = []
    output_calls: list[tuple[object, object, object]] = []
    clear_calls: list[object] = []
    shell = SimpleNamespace(
        clear_output_signal=_Signal(),
        progress_update_signal=_Signal(),
        preview_image_signal=_Signal(),
        add_output_image_signal=_Signal(),
        generation_feedback_presenter=SimpleNamespace(
            clear_output_for_workflow=clear_calls.append
        ),
        generation_action_controller=SimpleNamespace(
            update_progress_labels=lambda workflow, sampler: progress_calls.append(
                (workflow, sampler)
            )
        ),
        workspace_canvas_actions=SimpleNamespace(
            display_preview_image=preview_calls.append,
            handle_add_output_image=lambda workflow_id, image, metadata: (
                output_calls.append((workflow_id, image, metadata))
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_generation_feedback_signals()
    shell.clear_output_signal.fire("wf-a")
    shell.progress_update_signal.fire(0.25, None)
    shell.preview_image_signal.fire("preview")
    shell.add_output_image_signal.fire("wf-a", "image", "metadata")

    assert clear_calls == ["wf-a"]
    assert progress_calls == [(0.25, None)]
    assert preview_calls == ["preview"]
    assert output_calls == [("wf-a", "image", "metadata")]


def test_app_orb_menu_routes_file_actions_and_runtime_requests() -> None:
    """App-orb wiring should inject UI adapters and route runtime actions."""

    menu = _AppOrbMenu()
    enabled_calls: list[bool] = []
    load_calls: list[dict[str, object]] = []
    save_calls: list[str] = []
    save_as_calls: list[dict[str, object]] = []
    export_calls: list[dict[str, object]] = []
    settings_calls: list[str] = []
    comfy_settings_calls: list[str] = []
    gui_restart_calls: list[str] = []
    restart_calls: list[str] = []

    def direct_load(_path: Path) -> str:
        """Return a stable direct-workflow result for signal routing."""

        return "direct"

    def direct_can_load(_path: Path) -> bool:
        """Report direct-workflow support for signal routing."""

        return True

    shell = SimpleNamespace(
        _active_workspace_route=SETTINGS_WORKSPACE_ROUTE,
        shell_chrome_controller=SimpleNamespace(
            set_app_orb_workflow_file_actions_enabled=enabled_calls.append,
        ),
        workspace_controller=SimpleNamespace(
            on_settings_tab_selected=lambda: settings_calls.append("settings"),
        ),
        workspace_file_actions=SimpleNamespace(
            on_load_clicked=lambda **kwargs: load_calls.append(kwargs),
            on_save_clicked=lambda: save_calls.append("save"),
            on_save_as_clicked=lambda **kwargs: save_as_calls.append(kwargs),
            on_export_comfy_workflow_clicked=lambda **kwargs: export_calls.append(
                kwargs
            ),
        ),
        direct_workflow_file_actions=SimpleNamespace(
            load_document=direct_load,
            can_load_document=direct_can_load,
        ),
        comfy_runtime_actions=SimpleNamespace(
            open_comfyui_settings_webview=lambda: comfy_settings_calls.append(
                "comfy_settings"
            ),
            request_comfy_restart=lambda: restart_calls.append("restart"),
        ),
        request_full_gui_reload=lambda: gui_restart_calls.append("gui_restart"),
    )

    MainWindowSignalBinder(shell).attach_app_orb_menu(menu)
    menu.openRequested.fire()
    menu.saveRequested.fire()
    menu.saveAsRequested.fire()
    menu.exportRequested.fire()
    menu.settingsRequested.fire()
    menu.comfyUiSettingsRequested.fire()
    menu.restartGuiRequested.fire()
    menu.restartComfyRequested.fire()

    assert shell.appOrbMenuButton is menu
    assert enabled_calls == [False]
    assert load_calls == [
        {
            "file_dialog": QFileDialog,
            "cube_loader": load_cube_async,
            "icon_provider": FIF,
            "message_box": QMessageBox,
            "load_direct_workflow_document": direct_load,
            "can_load_direct_workflow_document": direct_can_load,
        }
    ]
    assert save_calls == ["save"]
    assert save_as_calls == [{"file_dialog": QFileDialog}]
    assert export_calls == [
        {
            "file_dialog": QFileDialog,
            "message_box": QMessageBox,
        }
    ]
    assert settings_calls == ["settings"]
    assert comfy_settings_calls == ["comfy_settings"]
    assert gui_restart_calls == ["gui_restart"]
    assert restart_calls == ["restart"]


def test_search_signals_route_callbacks_and_allow_missing_closed_signal() -> None:
    """Search wiring should connect search events and tolerate optional close signals."""

    events: list[tuple[str, object]] = []
    workspace_search_actions = SimpleNamespace(
        on_context_search_changed=lambda context, text: events.append(
            ("changed", (context, text))
        ),
        on_cycle_search_match=lambda: events.append(("next", None)),
        on_cycle_search_match_backward=lambda: events.append(("previous", None)),
        on_search_closed=lambda: events.append(("closed", None)),
    )
    shell = SimpleNamespace(
        contextSearchBox=SimpleNamespace(
            contextSearchChanged=_Signal(),
            cycleSearchMatchRequested=_Signal(),
            cycleSearchMatchRequestedBackward=_Signal(),
            closed=_Signal(),
        ),
        workspace_search_actions=workspace_search_actions,
    )
    shell_without_closed = SimpleNamespace(
        contextSearchBox=SimpleNamespace(
            contextSearchChanged=_Signal(),
            cycleSearchMatchRequested=_Signal(),
            cycleSearchMatchRequestedBackward=_Signal(),
        ),
        workspace_search_actions=workspace_search_actions,
    )

    MainWindowSignalBinder(shell).connect_search_signals()
    MainWindowSignalBinder(shell_without_closed).connect_search_signals()
    shell.contextSearchBox.contextSearchChanged.fire("Node", "ksampler")
    shell.contextSearchBox.cycleSearchMatchRequested.fire()
    shell.contextSearchBox.cycleSearchMatchRequestedBackward.fire()
    shell.contextSearchBox.closed.fire()

    assert events == [
        ("changed", ("Node", "ksampler")),
        ("next", None),
        ("previous", None),
        ("closed", None),
    ]


def test_workflow_tab_signals_route_events_and_tab_structure_autosave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow-tab wiring should route actions and autosave tab structure changes."""

    events: list[tuple[str, object]] = []
    autosaves: list[SessionAutosaveRequestCategory] = []
    delegated: list[dict[str, object]] = []

    def reopen_latest_closed_workflow() -> bool:
        """Record a successful reopen request."""

        events.append(("reopen", None))
        return True

    def materialize_loaded_cube_input_canvas(
        view: object,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Record the materialization adapter call."""

        events.append(("materialize", (view, workflow_id, cube_alias)))

    def duplicate_workflow_tab_for_view(**kwargs: object) -> None:
        """Record direct duplicate-owner routing from signal binding."""

        delegated.append(kwargs)
        events.append(("duplicate", kwargs["workflow_id"]))

    monkeypatch.setattr(
        signal_binder_mod,
        "duplicate_workflow_tab_for_view",
        duplicate_workflow_tab_for_view,
    )
    monkeypatch.setattr(
        signal_binder_mod,
        "materialize_loaded_cube_input_canvas_for_view",
        materialize_loaded_cube_input_canvas,
    )
    workflow_duplicate_service = SimpleNamespace(name="duplicate-service")
    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            workflowRenameRequested=_Signal(),
            workflowAddRequested=_Signal(),
            workflowSelected=_Signal(),
            workflowCloseRequested=_Signal(),
            workflowDuplicateRequested=_Signal(),
            workflowReopenClosedRequested=_Signal(),
        ),
        workflow_workspace=SimpleNamespace(
            rename_workflow=lambda workflow_id, name: events.append(
                ("rename", (workflow_id, name))
            ),
            add_workflow=lambda: events.append(("add", None)),
            activate_workflow=lambda workflow_id, *, source: events.append(
                ("selected", (workflow_id, source))
            ),
            close_workflow=lambda workflow_id: events.append(("close", workflow_id)),
            reopen_latest_closed_workflow=reopen_latest_closed_workflow,
        ),
        workflow_duplicate_service=workflow_duplicate_service,
        session_autosave_controller=SimpleNamespace(
            request_categorized_session_autosave=autosaves.append,
            request_tab_selection_autosave=lambda: events.append(
                ("selection_autosave", None)
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_workflow_tab_signals()
    shell.workflow_tabbar.workflowRenameRequested.fire("wf-a", "New Name")
    shell.workflow_tabbar.workflowAddRequested.fire()
    shell.workflow_tabbar.workflowSelected.fire("wf-b")
    shell.workflow_tabbar.workflowCloseRequested.fire("wf-c")
    shell.workflow_tabbar.workflowDuplicateRequested.fire("wf-d")
    shell.workflow_tabbar.workflowReopenClosedRequested.fire()

    assert events == [
        ("rename", ("wf-a", "New Name")),
        ("add", None),
        ("selected", ("wf-b", "workflow_tab")),
        ("selection_autosave", None),
        ("close", "wf-c"),
        ("duplicate", "wf-d"),
        ("reopen", None),
    ]
    assert autosaves == [
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
    ]
    assert delegated[0]["view"] is shell
    assert delegated[0]["workflow_workspace"] is shell.workflow_workspace
    assert delegated[0]["workflow_duplicate_service"] is workflow_duplicate_service
    assert delegated[0]["workflow_id"] == "wf-d"
    materialize = delegated[0]["materialize_loaded_cube_input_canvas"]
    assert callable(materialize)
    materialize("wf-copy", "CubeA")
    assert events[-1] == ("materialize", (shell, "wf-copy", "CubeA"))
    assert callable(delegated[0]["schedule_rehydration"])


def test_reopen_closed_workflow_autosaves_only_after_restore() -> None:
    """Reopen wiring should autosave only when a workflow is restored."""

    events: list[str] = []

    def reopen_successfully() -> bool:
        """Record a successful reopen request."""

        events.append("reopen")
        return True

    def skip_reopen() -> bool:
        """Record a reopen request that found no closed workflow."""

        events.append("reopen")
        return False

    shell = SimpleNamespace(
        workflow_workspace=SimpleNamespace(
            reopen_latest_closed_workflow=reopen_successfully,
        ),
        request_session_autosave=lambda: events.append("autosave"),
    )

    MainWindowSignalBinder(shell)._reopen_latest_closed_workflow()

    assert events == ["reopen", "autosave"]

    events.clear()
    shell.workflow_workspace = SimpleNamespace(
        reopen_latest_closed_workflow=skip_reopen,
    )

    MainWindowSignalBinder(shell)._reopen_latest_closed_workflow()

    assert events == ["reopen"]


def test_canvas_signals_route_output_events_and_canvas_selection_autosave() -> None:
    """Canvas wiring should route output events and categorize canvas autosaves."""

    events: list[tuple[str, object]] = []
    autosaves: list[SessionAutosaveRequestCategory] = []
    input_canvas = SimpleNamespace(
        inputMaskSaved=_Signal(),
        inputImageLoaded=_Signal(),
    )
    output_canvas = SimpleNamespace(
        activeOutputChanged=_Signal(),
        activeOutputGridChanged=_Signal(),
        activeOutputSceneChanged=_Signal(),
        activeOutputCompareChanged=_Signal(),
    )
    shell = SimpleNamespace(
        workspace_canvas_actions=SimpleNamespace(
            on_active_output_changed=lambda uuid_str: events.append(
                ("active_output", uuid_str)
            ),
            on_active_output_grid_changed=lambda source_key: events.append(
                ("active_output_grid", source_key)
            ),
            on_active_output_scene_changed=lambda selection: events.append(
                ("active_output_scene", selection)
            ),
            on_output_compare_changed=lambda compare_key: events.append(
                ("compare", compare_key)
            ),
        ),
        session_autosave_controller=SimpleNamespace(
            request_categorized_session_autosave=autosaves.append
        ),
    )

    MainWindowSignalBinder(shell).connect_canvas_signals(
        input_canvas=input_canvas,
        output_canvas=output_canvas,
    )
    output_canvas.activeOutputChanged.fire("out-1")
    output_canvas.activeOutputGridChanged.fire("source-a")
    scene_selection = OutputSceneNavigationSelection(
        scene_key="scene-a",
        overview=False,
        source_key="source-a",
        set_index=0,
        image_id=None,
    )
    output_canvas.activeOutputSceneChanged.fire(scene_selection)
    output_canvas.activeOutputCompareChanged.fire("compare-a")
    input_canvas.inputMaskSaved.fire("mask-1", "buffer.png")
    input_canvas.inputImageLoaded.fire("node-1", "input.png")

    assert events == [
        ("active_output", "out-1"),
        ("active_output_grid", "source-a"),
        ("active_output_scene", scene_selection),
        ("compare", "compare-a"),
    ]
    assert autosaves == [
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
        SessionAutosaveRequestCategory.CANVAS_SELECTION,
    ]


def test_editor_panel_signals_route_editor_events_and_layout_autosave() -> None:
    """Editor-panel wiring should bind image, mask, prompt, and layout events."""

    events: list[tuple[str, object]] = []
    editor_panel = SimpleNamespace(
        currentCubeVisibleChanged=_Signal(),
        inputImageChanged=_Signal(),
        inputImageClicked=_Signal(),
        inputMaskChanged=_Signal(),
        inputMaskClicked=_Signal(),
        promptSceneQueueRequested=_Signal(),
        promptEditorLayoutChanged=_Signal(),
    )
    shell = SimpleNamespace(
        workspace_cube_stack_actions=SimpleNamespace(
            highlight_tab_for_cube=lambda alias: events.append(("visible", alias)),
        ),
        workspace_scene_generation_actions=SimpleNamespace(
            enqueue_prompt_scene=lambda scene_key: events.append(
                ("prompt_scene", scene_key)
            ),
        ),
        input_canvas_presenter=SimpleNamespace(
            handle_input_image_changed=lambda alias, node, path: events.append(
                ("image_changed", (alias, node, path))
            ),
            handle_input_image_clicked=lambda alias, node, path: events.append(
                ("image_clicked", (alias, node, path))
            ),
            handle_input_mask_changed=lambda alias, node, path: events.append(
                ("mask_changed", (alias, node, path))
            ),
            handle_input_mask_clicked=lambda alias, node, path: events.append(
                ("mask_clicked", (alias, node, path))
            ),
        ),
        request_session_autosave=lambda: events.append(("autosave", None)),
    )

    MainWindowSignalBinder(shell).connect_editor_panel_signals(editor_panel)
    editor_panel.currentCubeVisibleChanged.fire("CubeA")
    editor_panel.inputImageChanged.fire("CubeA", "ImageNode", "image.png")
    editor_panel.inputImageClicked.fire("CubeA", "ImageNode", "image.png")
    editor_panel.inputMaskChanged.fire("CubeA", "MaskNode", "mask.png")
    editor_panel.inputMaskClicked.fire("CubeA", "MaskNode", "mask.png")
    editor_panel.promptSceneQueueRequested.fire("portrait")
    editor_panel.promptEditorLayoutChanged.fire()

    assert events == [
        ("visible", "CubeA"),
        ("image_changed", ("CubeA", "ImageNode", "image.png")),
        ("image_clicked", ("CubeA", "ImageNode", "image.png")),
        ("mask_changed", ("CubeA", "MaskNode", "mask.png")),
        ("mask_clicked", ("CubeA", "MaskNode", "mask.png")),
        ("prompt_scene", "portrait"),
        ("autosave", None),
    ]


def test_cube_stack_signals_route_stack_events_and_optional_signals() -> None:
    """Cube-stack wiring should defer picker dependencies to the picker action."""

    events: list[tuple[str, object]] = []
    wheel_events: list[object] = []
    cube_stack = SimpleNamespace(
        cubeRenameEditRequested=_Signal(),
        cubeRenameRequested=_Signal(),
        aliasEditingFinished=_Signal(),
        cubeMoveFinished=_Signal(),
        tabMouseReleased=_Signal(),
        cubeAddRequested=_Signal(),
        cubeCloseRequested=_Signal(),
        cubeDuplicateRequested=_Signal(),
        cubeBypassToggleRequested=_Signal(),
        cubeOutputPersistenceToggleRequested=_Signal(),
        cubeStackWheelRerouteRequested=_Signal(),
    )
    active_panel = SimpleNamespace(
        handle_external_wheel=lambda event: wheel_events.append(event)
    )
    shell = SimpleNamespace(
        active_editor_panel=active_panel,
        workspace_cube_picker_actions=SimpleNamespace(
            show_cube_picker=lambda: events.append(("picker", None)),
        ),
        workspace_cube_stack_actions=SimpleNamespace(
            on_cube_rename_edit_requested=lambda route_key: events.append(
                ("rename_edit", route_key)
            ),
            on_cube_rename_requested=lambda old_key, new_key, *, timer: events.append(
                ("renamed", (old_key, new_key, timer))
            ),
            on_cube_rename_edit_finished=lambda route_key: events.append(
                ("rename_edit_finished", route_key)
            ),
            on_cube_move_finished=lambda: events.append(("move_finished", None)),
            on_tab_mouse_released=lambda index: events.append(
                ("mouse_released", index)
            ),
            on_cube_close_requested=lambda index: events.append(("closed", index)),
            on_cube_duplicate_requested=lambda route_key: events.append(
                ("duplicate", route_key)
            ),
            on_cube_bypass_toggle_requested=lambda route_key: events.append(
                ("bypass", route_key)
            ),
            on_cube_output_persistence_toggle_requested=lambda route_key: events.append(
                ("output_persistence", route_key)
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_cube_stack_signals(cube_stack)
    wheel_event = object()
    cube_stack.cubeRenameEditRequested.fire("OldAlias")
    cube_stack.cubeRenameRequested.fire("OldAlias", "NewAlias")
    cube_stack.aliasEditingFinished.fire("OldAlias")
    cube_stack.cubeMoveFinished.fire()
    cube_stack.tabMouseReleased.fire(4)
    cube_stack.cubeAddRequested.fire()
    cube_stack.cubeCloseRequested.fire(3)
    cube_stack.cubeDuplicateRequested.fire("OldAlias")
    cube_stack.cubeBypassToggleRequested.fire("OldAlias")
    cube_stack.cubeOutputPersistenceToggleRequested.fire("OldAlias")
    cube_stack.cubeStackWheelRerouteRequested.fire(wheel_event)

    assert events == [
        ("rename_edit", "OldAlias"),
        ("renamed", ("OldAlias", "NewAlias", QTimer)),
        ("rename_edit_finished", "OldAlias"),
        ("move_finished", None),
        ("mouse_released", 4),
        ("picker", None),
        ("closed", 3),
        ("duplicate", "OldAlias"),
        ("bypass", "OldAlias"),
        ("output_persistence", "OldAlias"),
    ]
    assert wheel_events == [wheel_event]


def test_cube_stack_wheel_reroute_ignores_without_active_editor_panel() -> None:
    """Wheel rerouting should leave the event unhandled when no editor is active."""

    calls: list[str] = []
    shell = SimpleNamespace(active_editor_panel=None)
    event = SimpleNamespace(ignore=lambda: calls.append("ignored"))

    MainWindowSignalBinder(shell).route_cube_stack_wheel_to_editor_panel(event)

    assert calls == ["ignored"]
