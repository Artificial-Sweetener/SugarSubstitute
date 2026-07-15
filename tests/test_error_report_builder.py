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

"""Contract tests for structured error report rendering."""

from __future__ import annotations

from substitute.application.error_report_builder import ErrorReportBuilder
from substitute.application.errors import (
    DiagnosticSeverity,
    SubstituteOperationContext,
    build_cube_library_drift_report,
    build_comfy_connection_error_report,
    build_execution_error_report,
    build_prompt_validation_error_report,
    build_substitute_exception_report,
)


def test_execution_report_preserves_full_traceback_and_node_context() -> None:
    """Execution reports should keep Comfy traceback and node payload details."""

    report = build_execution_error_report(
        {
            "prompt_id": "pid-1",
            "node_id": "14",
            "node_type": "KSampler",
            "executed": ["1", "2"],
            "exception_type": "RuntimeError",
            "exception_message": "CUDA out of memory",
            "traceback": ["Traceback line 1", "Traceback line 2"],
            "current_inputs": {"seed": 123},
            "current_outputs": {"images": []},
        },
        workflow_id="wf-1",
    )

    rendered = ErrorReportBuilder().render(report)

    assert report.title == "KSampler failed"
    assert report.severity is DiagnosticSeverity.ERROR
    assert report.message == "CUDA out of memory"
    assert report.traceback == ("Traceback line 1", "Traceback line 2")
    assert report.node is not None
    assert report.node.node_id == "14"
    assert report.node.current_inputs == {"seed": 123}
    assert "Traceback line 1\nTraceback line 2" in rendered
    assert "Severity: error" in rendered
    assert "Node ID: 14" in rendered
    assert '"seed": 123' in rendered


def test_prompt_validation_report_preserves_node_errors() -> None:
    """Prompt validation reports should preserve Comfy node_errors entries."""

    report = build_prompt_validation_error_report(
        {
            "error": {
                "type": "prompt_outputs_failed_validation",
                "message": "Prompt outputs failed validation",
                "details": "KSampler input invalid",
            },
            "node_errors": {
                "14": {
                    "class_type": "KSampler",
                    "dependent_outputs": ["22"],
                    "errors": [
                        {
                            "type": "value_not_in_list",
                            "message": "Value not in list",
                            "details": "sampler_name",
                            "extra_info": {"input_name": "sampler_name"},
                        }
                    ],
                }
            },
        },
        workflow_id="wf-1",
        status_code=400,
        prompt_nodes={
            "14": {
                "class_type": "KSampler",
                "_meta": {
                    "title": "Anima/Promptmask Detailer.detailer",
                    "substitute": {
                        "cube_alias": "Anima/Promptmask Detailer",
                        "node_name": "detailer",
                    },
                },
            }
        },
    )

    rendered = ErrorReportBuilder().render(report)

    assert report.prompt_validation is not None
    assert report.prompt_validation.status_code == 400
    assert len(report.prompt_validation.node_errors) == 1
    assert report.prompt_validation.node_errors[0].class_type == "KSampler"
    assert report.prompt_validation.node_errors[0].cube_alias == (
        "Anima/Promptmask Detailer"
    )
    assert report.prompt_validation.node_errors[0].node_name == "detailer"
    assert report.prompt_validation.node_errors[0].messages[0].input_name == (
        "sampler_name"
    )
    assert "Prompt validation failed" in rendered
    assert "Node 14 - KSampler [Anima/Promptmask Detailer.detailer]" in rendered
    assert "sampler_name: Value not in list: sampler_name" in rendered


def test_substitute_exception_report_preserves_traceback_and_operation_context() -> (
    None
):
    """Substitute reports should include exception and operation diagnostics."""

    try:
        raise ValueError("bad recipe")
    except ValueError as error:
        report = build_substitute_exception_report(
            title="Recipe load failed",
            message="Substitute could not load the selected recipe.",
            stage="load_recipe",
            error=error,
            context=SubstituteOperationContext(
                operation="load_recipe",
                workflow_id="workflow_1",
                workflow_name="Untitled Workflow",
                path="E:\\recipes\\broken.sugar",
                values={
                    "z_value": {"nested": True},
                    "a_value": 3,
                },
            ),
        )

    rendered = ErrorReportBuilder().render(report)

    assert report.exception_type == "ValueError"
    assert report.workflow_id == "workflow_1"
    assert report.operation_context is not None
    assert report.operation_context.operation == "load_recipe"
    assert any("ValueError: bad recipe" in line for line in report.traceback)
    assert "Kind: substitute_internal" in rendered
    assert "Severity: error" in rendered
    assert "Substitute operation context" in rendered
    assert "Operation: load_recipe" in rendered
    assert "Workflow ID: workflow_1" in rendered
    assert "Workflow name: Untitled Workflow" in rendered
    assert "Path: E:\\recipes\\broken.sugar" in rendered
    assert rendered.index("A Value: 3") < rendered.index("Z Value:")
    assert "ValueError: bad recipe" in rendered


def test_comfy_connection_report_can_render_without_exception() -> None:
    """Connection reports should support known failures without traceback objects."""

    report = build_comfy_connection_error_report(
        title="Comfy is unavailable",
        message="The selected Comfy backend is not ready.",
        stage="preflight",
        context=SubstituteOperationContext(
            operation="start_generation",
            workflow_id="backend",
            values={"backend_state": "offline"},
        ),
    )

    rendered = ErrorReportBuilder().render(report)

    assert report.exception_type is None
    assert report.severity is DiagnosticSeverity.ERROR
    assert report.traceback == ()
    assert "Kind: comfy_connection" in rendered
    assert "Severity: error" in rendered
    assert "Message: The selected Comfy backend is not ready." in rendered
    assert "Backend State: offline" in rendered


def test_cube_library_drift_report_renders_warning_detail() -> None:
    """Cube Library drift should render as a warning with detailed cube messages."""

    report = build_cube_library_drift_report(
        (
            "Cube 'CubeA' (Owner/Repo/CubeA.cube) was saved from an uncommitted Cube Library artifact.",
            "Cube 'CubeB' (Owner/Repo/CubeB.cube) was saved from an uncommitted Cube Library artifact.",
        ),
        context=SubstituteOperationContext(
            operation="load_recipe_cube_library_drift",
            workflow_id="workflow_1",
            path="E:\\recipes\\image.png",
            values={"message_count": 2},
        ),
    )

    rendered = ErrorReportBuilder().render(report)

    assert report.severity is DiagnosticSeverity.WARNING
    assert report.title == "Cube Library Notice"
    assert report.message == "The recipe loaded with Cube Library warnings."
    assert "Severity: warning" in rendered
    assert "Kind: cube_library_drift" in rendered
    assert "Cube Library warnings" in rendered
    assert "Cube 'CubeA'" in rendered
    assert "Path: E:\\recipes\\image.png" in rendered
    assert "Message Count: 2" in rendered
