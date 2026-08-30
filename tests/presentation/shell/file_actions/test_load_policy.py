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

"""Test recipe load cancellation and naming policy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _EditorBusyRecorder,
    _noop_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_on_load_clicked_does_not_create_workflow_when_selection_is_cancelled(
    tmp_path: Path,
) -> None:
    """Cancelling file selection should not create an empty workflow tab."""

    mod = _import_module()
    current_id = "wf-1"
    new_id = "wf-2"
    current_tab = _TabItem(current_id, "Recipe 1")
    new_tab = _TabItem(new_id, "Untitled Workflow 2")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    add_calls: list[str] = []
    sugar_scripts_dir = tmp_path / "sugarscripts"
    opened_directories: list[str] = []

    workflows = {
        current_id: SimpleNamespace(stack_order=["CubeA"], cubes={"CubeA": object()}),
        new_id: SimpleNamespace(stack_order=[], cubes={}, global_overrides={}),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: current_tab,
            itemMap={current_id: current_tab, new_id: new_tab},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows=workflows,
            get_workflow=lambda workflow_id: workflows.get(workflow_id),
        ),
        recipe_io_service=SimpleNamespace(),
        cube_stacks={new_id: cube_stack},
        editor_panels={new_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=sugar_scripts_dir,
            cubes_dir=tmp_path / "cubes",
        ),
    )

    def _add_workflow() -> None:
        add_calls.append("added")
        view.workflow_session_service.active_workflow_id = new_id

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            _parent: object,
            _caption: str,
            directory: str,
            _filter: str,
            **_kwargs: object,
        ) -> tuple[str, str]:
            opened_directories.append(directory)
            return "", ""

    actions.on_load_clicked(
        projects_dir=tmp_path,
        sugar_scripts_dir=sugar_scripts_dir,
        file_dialog=_Dialog,
    )

    assert add_calls == []
    assert opened_directories == [str(sugar_scripts_dir)]


def test_on_load_clicked_migrates_legacy_default_project_name_for_new_tab(
    tmp_path: Path,
) -> None:
    """Loaded legacy default project names should use current workflow labels."""

    mod = _import_module()
    current_id = "wf-1"
    new_id = "wf-2"
    current_tab = _TabItem(current_id, "Untitled Workflow")
    new_tab = _TabItem(new_id, "Untitled Workflow (2)")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.png"
    loader_calls: list[dict[str, object]] = []

    workflows = {
        current_id: SimpleNamespace(
            stack_order=["CubeA"],
            cubes={"CubeA": object()},
        ),
        new_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        ),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: current_tab,
            itemMap={current_id: current_tab, new_id: new_tab},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows=workflows,
            get_workflow=lambda workflow_id: workflows.get(workflow_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={},
                    project_name="Untitled Recipe",
                ),
            )
        ),
        cube_stacks={new_id: cube_stack},
        editor_panels={new_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda _path: None,
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )

    def _add_workflow() -> None:
        view.workflow_session_service.active_workflow_id = new_id

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: _append(
            loader_calls,
            {"callbacks": callbacks, **kwargs},
        ),
        icon_provider=_IconProvider,
    )

    assert new_tab.text() == "Untitled Workflow (2)"
    assert loader_calls[0]["cube_id"] == "LoaderCube"
