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

"""Test loaded recipe workspace materialization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, cast


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _append_then,
    _EditorBusyRecorder,
    _recipe_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_on_load_clicked_reuses_blank_default_workflow_and_restores_output(
    tmp_path: Path,
) -> None:
    """Loading into the default blank workflow should reuse it and restore PNG output."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    add_workflow_calls: list[str] = []
    loader_calls: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    added_outputs: list[tuple[str, object, object]] = []
    loaded_image_calls: list[Path] = []
    source_path = tmp_path / "recipe.png"
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={"seed": 7},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=SimpleNamespace(
            apply_global_overrides=lambda: _append(
                add_workflow_calls,
                "overrides",
            )
        ),
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: _append_then(
                loaded_image_calls,
                path,
                "qimg",
            ),
            build_output_image_metadata=lambda **_kwargs: "meta",
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(cast(list[object], busy_calls)),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: _append(
            add_workflow_calls,
            "new-workflow",
        ),
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
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
            {
                "callbacks": callbacks,
                **kwargs,
            },
        ),
        icon_provider=_IconProvider,
    )

    assert add_workflow_calls == ["overrides"]
    assert tab_item.text() == "Loaded Workflow"
    assert cube_stack.cleared == 1
    assert editor_panel.clear_calls == 1
    assert view._pending_cubes == {"CubeA": 0}
    assert loader_calls == [
        {
            "callbacks": "callbacks",
            "cube_id": "LoaderCube",
            "alias_name": "CubeA",
            "placeholder_index": 0,
            "buffer_patch": {"cube_id": "LoaderCube"},
            "reveal_after_load": False,
            "presentation_intent": loader_calls[0]["presentation_intent"],
            "on_load_finished": loader_calls[0]["on_load_finished"],
        }
    ]
    presentation_intent = cast(Any, loader_calls[0]["presentation_intent"])
    assert presentation_intent.select_after_load is False
    assert presentation_intent.scroll_after_load is False
    assert busy_calls == [("begin", (workflow_id, "Loading"))]
    finish_load = cast(
        Callable[[str | None], None], loader_calls[0]["on_load_finished"]
    )
    finish_load("CubeA")
    assert busy_calls == [
        ("begin", (workflow_id, "Loading")),
        ("end", "busy-token"),
    ]
    assert loaded_image_calls == [source_path]
    assert added_outputs == [(workflow_id, "qimg", "meta")]
