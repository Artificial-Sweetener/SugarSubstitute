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

"""Cube-picker catalog and queue error-presentation contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from substitute.application.cubes import (
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.application.ports import CubeCatalogSnapshot


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _EditorBusyRecorder,
    _import_module,
)


def test_show_cube_picker_queue_failure_uses_default_error_presenter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue failures should lazily resolve the copyable application error modal."""

    mod = _import_module()
    stack = _CubeStack()
    busy_calls: list[tuple[str, object]] = []
    presented: list[dict[str, Any]] = []
    record = CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A")
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(list_available_cubes=lambda: [record]),
        cube_stack_service=SimpleNamespace(
            resolve_unique_alias=lambda _workflow, seed: seed
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
        _pending_cubes={},
        editor_busy=_EditorBusyRecorder(busy_calls),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )
    monkeypatch.setattr(
        mod,
        "ErrorPresenter",
        lambda *, parent: SimpleNamespace(
            parent=parent,
            show_exception_report=lambda **kwargs: presented.append(kwargs),
        ),
    )

    class _Picker:
        @staticmethod
        def stage_cubes(**_kwargs: object) -> object:
            return cube_stack_draft_result(
                [cube_stack_draft_entry_from_record(record, draft_id="copy-a")]
            )

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    def _raise_loader(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("queue failed")

    actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=_IconProvider,
        cube_loader=_raise_loader,
    )

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    assert presented[0]["title"] == "Staged cube queue failed"
    assert presented[0]["stage"] == "cube_load"
    assert str(presented[0]["error"]) == "queue failed"
    assert presented[0]["context"].operation == "queue_staged_cubes"


def test_show_cube_picker_list_failure_reports_through_error_presenter() -> None:
    """Cube catalog failures should use the unified error modal presenter."""

    mod = _import_module()
    stack = _CubeStack()
    presented: list[dict[str, Any]] = []
    failure = RuntimeError("catalog unavailable")
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_load_service=SimpleNamespace(
            list_available_cubes=lambda: (_ for _ in ()).throw(failure)
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    actions.show_cube_picker()

    assert presented[0]["title"] == "Cube picker failed"
    assert presented[0]["stage"] == "cube_picker"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "list_cubes_for_picker"
    assert context.workflow_id == "wf-a"
    assert context.trace_id


def test_show_cube_picker_missing_catalog_refresh_error_does_not_open_empty_picker() -> (
    None
):
    """Unavailable catalog snapshots should fail loudly instead of showing no cubes."""

    mod = _import_module()
    stack = _CubeStack()
    presented: list[dict[str, Any]] = []
    picker_calls: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[],
                state="missing",
            ),
            refresh_picker_catalog=lambda: CubeCatalogSnapshot(
                entries=[],
                state="error",
                error="backend refused connection",
            ),
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: presented.append(kwargs)
        ),
    )

    class _Picker:
        @staticmethod
        def select_cube(**_kwargs: object) -> CubeCatalogRecord | None:
            picker_calls.append("opened")
            return None

    actions.show_cube_picker(
        cube_picker=_Picker,
    )

    assert picker_calls == []
    assert presented[0]["title"] == "Cube picker failed"
    assert presented[0]["stage"] == "cube_picker"
    assert str(presented[0]["error"]) == "backend refused connection"
    context = presented[0]["context"]
    assert context.operation == "list_cubes_for_picker"
    assert context.workflow_id == "wf-a"
    assert context.values["catalog_state"] == "error"


def test_show_cube_picker_missing_catalog_refresh_success_opens_with_records() -> None:
    """Cold cache opens should recover when the synchronous refresh gets records."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    refreshed: list[str] = []

    def refresh_picker_catalog() -> CubeCatalogSnapshot:
        """Record catalog refresh and return fresh entries."""
        refreshed.append("refresh")
        return CubeCatalogSnapshot(entries=catalog, state="fresh")

    view = SimpleNamespace(
        active_cube_stack=stack,
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=[],
                state="missing",
            ),
            refresh_picker_catalog=refresh_picker_catalog,
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )

    class _Picker:
        records: list[CubeCatalogRecord] = []

        @staticmethod
        def select_cube(**kwargs: object) -> CubeCatalogRecord | None:
            records = kwargs["records"]
            assert isinstance(records, list)
            _Picker.records = records
            return None

    actions.show_cube_picker(cube_picker=_Picker)

    assert refreshed == ["refresh"]
    assert _Picker.records == catalog
