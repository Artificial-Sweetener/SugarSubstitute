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

"""Test output-save plan seed and cube-number policy."""

from __future__ import annotations

from __future__ import annotations
from types import SimpleNamespace
from substitute.application.generation import (
    ComfyAssetStagingResult,
    PreparedGenerationRequest,
)
from substitute.application.ports import (
    QueuePromptResult,
)

from tests.application.generation.generation_service.support import (
    _CallbackRecorder,
    _FakeRecipeIoService,
    _FakeWorkflowExportService,
    _FakeGateway,
    _FakeAssetStagingService,
    _build_generation_callbacks,
    _as_json_object,
    _build_generation_service,
)


def test_run_prepared_generation_output_save_plan_prefers_global_seed() -> None:
    """Output save plan seed should prefer the prepared Sugar global override."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler", "inputs": {"seed": 999}}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\nset *.*.seed = 1234\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.seed == "1234"


def test_run_prepared_generation_output_save_plan_numbers_cubes_from_script() -> None:
    """Prepared SugarScript dispatch should preserve cube order for output names."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text=(
                'use "cube" as "Text to Image"\nuse "cube" as "Diffusion Upscale"\n'
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["Text to Image"] == 1
    assert save_plan.cube_numbers_by_alias["Diffusion Upscale"] == 2


def test_run_prepared_generation_output_save_plan_skips_bypassed_script_cubes() -> None:
    """Prepared SugarScript dispatch should number only active cubes."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text=(
                'use "cube" as A\n'
                '# bypass use "cube" as B\n'
                'use "cube" as C\n'
                "connect A.output.image to C.input.image\n"
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["A"] == 1
    assert "B" not in save_plan.cube_numbers_by_alias
    assert save_plan.cube_numbers_by_alias["C"] == 2


def test_run_prepared_generation_output_save_plan_skips_bypassed_workflow_cubes() -> (
    None
):
    """Live workflow cube numbering should use active execution projection."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(
            {"N1": {"class_type": "KSampler"}}
        ),
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\nuse "cube" as C\n',
            workflow=SimpleNamespace(
                stack_order=["A", "B", "C"],
                cubes={
                    "A": SimpleNamespace(bypassed=False),
                    "B": SimpleNamespace(bypassed=True),
                    "C": SimpleNamespace(bypassed=False),
                },
            ),
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.cube_numbers_by_alias["A"] == 1
    assert "B" not in save_plan.cube_numbers_by_alias
    assert save_plan.cube_numbers_by_alias["C"] == 2


def test_run_prepared_generation_fails_when_all_cubes_are_bypassed() -> None:
    """A prepared workflow with no active cubes should fail before backend compile."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    export_service = _FakeWorkflowExportService({"N1": {"class_type": "KSampler"}})
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=export_service,
        comfy_gateway=fake_gateway,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='# bypass use "cube" as Muted\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is False
    assert export_service.calls == []
    assert "no active cubes" in recorder.failures[0].message


def test_run_prepared_generation_output_save_plan_uses_staged_workflow_seed() -> None:
    """Workflow seed fallback should be resolved after asset staging."""

    recorder = _CallbackRecorder([], [], [], [], [], [])
    fake_gateway = _FakeGateway(
        queue_results=[
            QueuePromptResult(
                status="queued",
                prompt_id="pid-1",
                payload={"prompt_id": "pid-1"},
                error=None,
            )
        ]
    )
    compiled_payload = {"N1": {"class_type": "KSampler", "inputs": {"seed": 111}}}
    staged_payload = {"N1": {"class_type": "KSampler", "inputs": {"seed": 222}}}
    asset_staging_service = _FakeAssetStagingService(
        ComfyAssetStagingResult(
            workflow_payload=_as_json_object(staged_payload),
            staged_assets=(),
            failures=(),
        )
    )
    service = _build_generation_service(
        recipe_io_service=_FakeRecipeIoService(),
        workflow_export_service=_FakeWorkflowExportService(compiled_payload),
        comfy_gateway=fake_gateway,
        asset_staging_service=asset_staging_service,
    )

    result = service.run_prepared_generation(
        request=PreparedGenerationRequest(
            workflow_id="wf-1",
            workflow_name="Workflow 1",
            sugar_script_text='use "cube" as A\n',
        ),
        callbacks=_build_generation_callbacks(recorder),
    )

    assert result.started is True
    save_plan = fake_gateway.listener_requests[0].output_save_plan
    assert save_plan is not None
    assert save_plan.seed == "222"
