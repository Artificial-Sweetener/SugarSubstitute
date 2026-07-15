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

"""Contract tests for modal error presentation routing."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.errors import (
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.presentation.errors import ErrorPresenter


class _Dialog:
    """Test dialog double that records modal execution."""

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def exec(self) -> None:
        """Record modal execution."""

        self._calls.append("exec")


def test_error_presenter_renders_and_executes_modal_dialog() -> None:
    """Structured reports should be presented through a modal dialog factory."""

    dialog_calls: list[str] = []
    factory_calls: list[tuple[object | None, ErrorReport, str, object | None]] = []
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="CUDA out of memory",
        stage="listen",
        prompt_id="pid-1",
    )

    def _factory(
        parent: object | None,
        error_report: ErrorReport,
        report_text: str,
        open_console: Callable[[], None] | None,
    ) -> _Dialog:
        factory_calls.append((parent, error_report, report_text, open_console))
        return _Dialog(dialog_calls)

    presenter = ErrorPresenter(parent="main", dialog_factory=_factory)

    presenter.show_error_report(report)

    assert dialog_calls == ["exec"]
    assert factory_calls[0][0] == "main"
    assert factory_calls[0][1] is report
    assert "CUDA out of memory" in factory_calls[0][2]


def test_error_presenter_deduplicates_active_report() -> None:
    """A report already being shown should not open a duplicate modal."""

    dialog_calls: list[str] = []
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="CUDA out of memory",
        stage="listen",
        prompt_id="pid-1",
    )
    presenter = ErrorPresenter(
        dialog_factory=lambda *_args: _Dialog(dialog_calls),
    )
    presenter._active_report_keys.add(
        ("error", "execution", "pid-1", "CUDA out of memory")
    )

    presenter.show_error_report(report)

    assert dialog_calls == []


def test_error_presenter_builds_substitute_exception_report() -> None:
    """Presenter should build local exception reports for UI collaborators."""

    dialog_calls: list[str] = []
    factory_calls: list[tuple[object | None, ErrorReport, str, object | None]] = []

    def _factory(
        parent: object | None,
        error_report: ErrorReport,
        report_text: str,
        open_console: Callable[[], None] | None,
    ) -> _Dialog:
        factory_calls.append((parent, error_report, report_text, open_console))
        return _Dialog(dialog_calls)

    presenter = ErrorPresenter(parent="main", dialog_factory=_factory)

    try:
        raise RuntimeError("cannot write file")
    except RuntimeError as error:
        presenter.show_exception_report(
            title="Export failed",
            message="Substitute could not export the workflow.",
            stage="export",
            error=error,
            context=SubstituteOperationContext(
                operation="export_workflow_json",
                workflow_id="wf-1",
                path="E:\\out\\workflow.json",
            ),
        )

    assert dialog_calls == ["exec"]
    assert factory_calls[0][1].kind is ErrorReportKind.SUBSTITUTE_INTERNAL
    assert factory_calls[0][1].exception_type == "RuntimeError"
    assert "Operation: export_workflow_json" in factory_calls[0][2]
    assert "Path: E:\\out\\workflow.json" in factory_calls[0][2]
    assert "RuntimeError: cannot write file" in factory_calls[0][2]


def test_error_presenter_builds_comfy_connection_report() -> None:
    """Presenter should build connection reports without requiring an exception."""

    dialog_calls: list[str] = []
    factory_calls: list[tuple[object | None, ErrorReport, str, object | None]] = []

    def _factory(
        parent: object | None,
        error_report: ErrorReport,
        report_text: str,
        open_console: Callable[[], None] | None,
    ) -> _Dialog:
        factory_calls.append((parent, error_report, report_text, open_console))
        return _Dialog(dialog_calls)

    presenter = ErrorPresenter(dialog_factory=_factory)

    presenter.show_comfy_connection_report(
        title="Comfy is unavailable",
        message="The backend is not ready.",
        stage="preflight",
        context=SubstituteOperationContext(
            operation="start_generation",
            workflow_id="backend",
        ),
    )

    assert dialog_calls == ["exec"]
    assert factory_calls[0][1].kind is ErrorReportKind.COMFY_CONNECTION
    assert "Kind: comfy_connection" in factory_calls[0][2]
    assert "Operation: start_generation" in factory_calls[0][2]
