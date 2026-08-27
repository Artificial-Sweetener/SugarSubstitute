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

"""Test loaded recipe cube reveal coordination."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _EditorBusyRecorder,
    _noop_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_on_load_clicked_batches_recipe_cube_reveal_until_all_loads_finish(
    tmp_path: Path,
) -> None:
    """Recipe loads should suppress per-cube reveal and activate once at batch end."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.sugar"
    loader_calls: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    activated: list[tuple[str, str]] = []
    callbacks = SimpleNamespace(
        activate_loaded_cube=lambda workflow_id, alias: _append(
            activated,
            (workflow_id, alias),
        )
    )
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
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={
                        "CubeA": {"cube_id": "LoaderCubeA"},
                        "CubeB": {"cube_id": "LoaderCubeB"},
                    },
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
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
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: callbacks,
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

    assert [call["reveal_after_load"] for call in loader_calls] == [False, False]
    assert activated == []

    first_finished = cast(
        Callable[[str | None], None], loader_calls[0]["on_load_finished"]
    )
    second_finished = cast(
        Callable[[str | None], None],
        loader_calls[1]["on_load_finished"],
    )
    assert callable(first_finished)
    assert callable(second_finished)
    first_finished("CubeA")
    assert activated == []
    assert busy_calls == [("begin", (workflow_id, "Loading"))]
    second_finished("CubeB")

    assert activated == [(workflow_id, "CubeB")]
    assert busy_calls == [
        ("begin", (workflow_id, "Loading")),
        ("end", "busy-token"),
    ]
