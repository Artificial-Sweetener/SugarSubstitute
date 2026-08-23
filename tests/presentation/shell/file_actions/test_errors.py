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

"""Test workspace file action failure and snapshot handling."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _append_then,
    _noop_output_registrar,
    _TabItem,
)


def test_on_load_clicked_reports_failure_through_error_presenter(
    tmp_path: Path,
) -> None:
    """Recipe load failures should use the unified error modal presenter."""

    mod = _import_module()
    source_path = tmp_path / "broken.sugar"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("bad")
    presented: list[dict[str, Any]] = []
    critical_calls: list[object] = []
    failure = ValueError("bad recipe")
    current_id = "wf-1"
    tab = _TabItem(current_id, "Untitled Workflow")
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab,
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows={
                current_id: SimpleNamespace(
                    stack_order=[],
                    cubes={},
                    global_overrides={},
                )
            },
            get_workflow=lambda workflow_id: (
                SimpleNamespace(
                    stack_order=[],
                    cubes={},
                    global_overrides={},
                )
                if workflow_id == current_id
                else None
            ),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: (_ for _ in ()).throw(failure)
        ),
        cube_stacks={},
        editor_panels={},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path, sugar_scripts_dir=tmp_path / "sugarscripts"
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: _append(presented, kwargs)
        ),
    )

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=SimpleNamespace(
            getOpenFileName=lambda *_args, **_kwargs: (
                str(source_path),
                "Recipes and Images",
            )
        ),
        message_box=SimpleNamespace(
            critical=lambda *args, **_kwargs: _append(critical_calls, args)
        ),
    )

    assert critical_calls == []
    assert presented[0]["title"] == "Load recipe failed"
    assert presented[0]["stage"] == "load"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "load_recipe"
    assert context.workflow_id == current_id
    assert context.path == str(source_path.resolve())


def test_open_sugar_snapshot_as_new_workflow_materializes_unique_tab(
    tmp_path: Path,
) -> None:
    """Snapshot open should create a new workflow and materialize parsed buffers."""

    mod = _import_module()
    inserted: list[dict[str, object]] = []
    loaded: list[dict[str, object]] = []
    calls: list[str] = []

    class _CubeStack:
        """Minimal cube stack for snapshot materialization."""

        def __init__(self) -> None:
            """Initialize tab item collection."""

            self.items: list[object] = []

        def clear(self) -> None:
            """Record clear."""

            calls.append("clear-stack")

        def count(self) -> int:
            """Return current item count."""

            return len(self.items)

        def insertTab(self, index: int, **kwargs: object) -> object:
            """Insert and return placeholder item."""

            item = object()
            self.items.insert(index, item)
            inserted.append(kwargs)
            return item

        def setCurrentIndex(self, index: int) -> None:
            """Record current index."""

            calls.append(f"current:{index}")

    class _EditorPanel:
        """Minimal editor panel for snapshot materialization."""

        def clear_layout(self) -> None:
            """Record layout clear."""

            calls.append("clear-editor")

    class _Icon:
        """Placeholder icon provider token."""

        def icon(self) -> object:
            """Return icon payload."""

            return "icon"

    active_id = {"value": "wf-a"}
    tab_items = {
        "wf-existing": _TabItem("wf-existing", "Recipe"),
        "wf-a": _TabItem("wf-a", "Untitled Workflow"),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(itemMap=tab_items),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={
                "wf-a": SimpleNamespace(global_overrides={}),
            },
        ),
        recipe_io_service=SimpleNamespace(
            parse_recipe_script=lambda _text: SimpleNamespace(
                buffers={
                    "A": {
                        "cube_id": "cube-a",
                    }
                },
                global_overrides={"seed": 1},
                project_name=None,
            )
        ),
        cube_stacks={"wf-a": _CubeStack()},
        editor_panels={"wf-a": _EditorPanel()},
        active_override_manager=SimpleNamespace(
            apply_global_overrides=lambda: _append(calls, "overrides")
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path,
        ),
        editor_busy=SimpleNamespace(
            begin=lambda workflow_id, *, message="Loading": _append_then(
                calls,
                f"busy:{workflow_id}:{message}",
                object(),
            ),
            end=lambda _token: _append(calls, "busy:end"),
            set_cancel_callback=lambda _token, _callback: None,
            update_download=lambda _token, _state: None,
        ),
    )

    def _add_workflow() -> None:
        """Activate the prepared workflow double."""

        view.workflow_session_service.active_workflow_id = active_id["value"]

    def _cube_loader(callbacks: object, **kwargs: object) -> None:
        """Record cube load request and finish synchronously."""

        del callbacks
        loaded.append(kwargs)
        on_load_finished = kwargs.get("on_load_finished")
        if callable(on_load_finished):
            on_load_finished("A")

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda workflow_id, alias: _append(
                calls,
                f"activate:{workflow_id}:{alias}",
            )
        ),
        output_image_registrar=_noop_output_registrar(),
    )

    opened_id = actions.open_sugar_snapshot_as_new_workflow(
        workflow_name="Recipe",
        sugar_script_text="# sugar",
        projects_dir=tmp_path,
        icon_provider=SimpleNamespace(CLOSE=_Icon()),
        cube_loader=_cube_loader,
    )

    assert opened_id == "wf-a"
    assert tab_items["wf-a"].text() == "Recipe (2)"
    assert view.workflow_session_service.workflows["wf-a"].global_overrides == {
        "seed": 1
    }
    assert inserted[0]["routeKey"] == "loading:A"
    assert loaded[0]["cube_id"] == "cube-a"
