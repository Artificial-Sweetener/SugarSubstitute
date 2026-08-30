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

"""Test cube-library drift presentation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _append_then,
    _EditorBusyRecorder,
    _noop_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_on_load_clicked_logs_recipe_cube_library_drift_without_dialog(
    tmp_path: Path,
) -> None:
    """Recipe loads should present Cube Library drift through the error modal system."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.sugar"
    warning_calls: list[tuple[object, str, str]] = []
    presented_reports: list[Any] = []
    drift_buffers: list[object] = []
    loader_calls: list[dict[str, object]] = []
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
                        "CubeA": {
                            "cube_id": "Owner/Repo/cube-a.cube",
                        }
                    },
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_library_management_service=SimpleNamespace(
            recipe_drift_messages=lambda buffers: _append_then(
                drift_buffers,
                buffers,
                ("Cube 'CubeA' changed.",),
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
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda *_args: None
        ),
        output_image_registrar=_noop_output_registrar(),
        error_presenter=SimpleNamespace(
            show_error_report=lambda report: _append(presented_reports, report)
        ),
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

    message_box = SimpleNamespace(
        critical=lambda *_args, **_kwargs: None,
        warning=lambda *args: _append(
            warning_calls,
            cast(tuple[object, str, str], args),
        ),
    )

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: loader_calls.append(
            {"callbacks": callbacks, **kwargs}
        ),
        icon_provider=_IconProvider,
        message_box=message_box,
    )

    assert drift_buffers == [
        {
            "CubeA": {
                "cube_id": "Owner/Repo/cube-a.cube",
            }
        }
    ]
    assert warning_calls == []
    assert len(presented_reports) == 1
    assert presented_reports[0].kind.value == "cube_library_drift"
    assert presented_reports[0].severity.value == "warning"
    assert presented_reports[0].title == "Cube Library Notice"
    assert presented_reports[0].message == (
        "The recipe loaded with Cube Library warnings."
    )
    assert presented_reports[0].operation_context.operation == (
        "load_recipe_cube_library_drift"
    )
    assert presented_reports[0].operation_context.path == str(source_path)
    assert loader_calls[0]["cube_id"] == "Owner/Repo/cube-a.cube"


def test_on_load_clicked_uses_error_presenter_fallback_for_cube_library_drift(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Cube Library drift should still use the error modal system without injection."""

    mod = _import_module()
    workflow_id = "wf-1"
    source_path = tmp_path / "recipe.sugar"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    presented_reports: list[Any] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    class _Presenter:
        def __init__(self, *, parent: object | None = None) -> None:
            self.parent = parent

        def show_error_report(self, report: object) -> None:
            """Record fallback modal presentation."""

            _append(presented_reports, report)

    monkeypatch.setattr(mod, "ErrorPresenter", _Presenter)
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
                    buffers={"CubeA": {"cube_id": "Owner/Repo/cube-a.cube"}},
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_library_management_service=SimpleNamespace(
            recipe_drift_messages=lambda _buffers: ("Cube 'CubeA' changed.",)
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
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda *_args: None
        ),
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
        cube_loader=lambda *_args, **_kwargs: None,
        icon_provider=_IconProvider,
    )

    assert len(presented_reports) == 1
    assert presented_reports[0].kind.value == "cube_library_drift"
    assert presented_reports[0].severity.value == "warning"
