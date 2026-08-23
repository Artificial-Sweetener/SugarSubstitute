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

"""Cube-picker live, cached, and background-refresh contracts."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from substitute.application.cubes import (
    cube_stack_draft_entry_from_record,
    cube_stack_draft_result,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.application.ports import CubeCatalogSnapshot
from substitute.presentation.errors import ErrorPresenter


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _EditorBusyRecorder,
    _import_module,
)


def test_show_cube_picker_queue_failure_reports_through_error_presenter() -> None:
    """Staged queue failures should produce a complete copyable error report."""

    mod = _import_module()
    stack = _CubeStack()
    busy_calls: list[tuple[str, object]] = []
    presented: list[tuple[Any, str]] = []
    record = CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="A")
    failure = RuntimeError("queue failed")

    def _dialog_factory(
        _parent: object | None,
        report: Any,
        report_text: str,
        _open_console: Callable[[], None] | None,
    ) -> object:
        """Capture the report payload used by the standard copy-report dialog."""

        presented.append((report, report_text))
        return SimpleNamespace(exec=lambda: None)

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
        error_presenter=ErrorPresenter(
            parent=None,
            dialog_factory=_dialog_factory,
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
        raise failure

    actions.show_cube_picker(
        cube_picker=_Picker,
        icon_provider=_IconProvider,
        cube_loader=_raise_loader,
    )

    assert busy_calls == [
        ("begin", ("wf-a", "Loading")),
        ("end", "busy-token"),
    ]
    report, report_text = presented[0]
    assert report.title == "Staged cube queue failed"
    assert report.stage == "cube_load"
    context = report.operation_context
    assert context is not None
    assert context.operation == "queue_staged_cubes"
    assert context.workflow_id == "wf-a"
    assert context.values["failed_queue_count"] == 1
    assert context.values["staged_count"] == 1
    assert "Operation: queue_staged_cubes" in report_text
    assert "Workflow ID: wf-a" in report_text
    assert "Failed Queue Count: 1" in report_text
    assert "RuntimeError: queue failed" in report_text


def test_show_cube_picker_uses_warm_snapshot_without_blocking_list() -> None:
    """Warm picker opens should use cached snapshot data immediately."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    list_calls: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=catalog,
                state="fresh",
            ),
            list_available_cubes=lambda: list_calls.append("list"),
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

    assert _Picker.records == catalog
    assert list_calls == []


def test_show_cube_picker_schedules_background_refresh_for_stale_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale warm catalog data should show immediately and refresh in background."""

    mod = _import_module()
    stack = _CubeStack()
    catalog = [
        CubeCatalogRecord(cube_id="base_a", version="1.0.0", display_name="Loader")
    ]
    scheduled: list[str] = []
    view = SimpleNamespace(
        active_cube_stack=stack,
        cube_icon_factory=object(),
        cube_load_service=SimpleNamespace(
            picker_catalog_snapshot=lambda: CubeCatalogSnapshot(
                entries=catalog,
                state="stale",
            ),
        ),
        get_active_workflow=lambda: SimpleNamespace(cubes={}, stack_order=[]),
    )
    actions = mod.WorkspaceCubePickerActions(
        view,
        build_cube_load_ui_callbacks=lambda: "callbacks",
    )
    monkeypatch.setattr(
        actions,
        "_schedule_catalog_refresh",
        lambda trace_id: scheduled.append(trace_id),
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

    assert _Picker.records == catalog
    assert len(scheduled) == 1
