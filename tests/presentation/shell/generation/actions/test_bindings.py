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

"""Tests for workspace generation action binding helpers."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.generation import (
    GenerationRequest,
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.common import GlobalOverrideScope
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workspace_generation_action_adapter import (
    GenerationActionBindingView,
    build_generation_action_bindings,
)
from substitute.presentation.shell.workspace_generation_controller import (
    QueuedGenerationPreparationJob,
)


from tests.presentation.shell.generation.actions.support import (
    _dispatcher,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_action_adapter.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def test_build_generation_action_bindings_routes_feedback_and_rearms_on_request() -> (
    None
):
    """Generation bindings should preserve request values until explicitly rearmed."""

    dispatcher = _dispatcher()
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, SimpleNamespace()),
    )
    randomizer_calls = 0

    view = SimpleNamespace(
        generation_feedback_dispatcher=dispatcher,
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        editor_panels={
            "workflow-a": SimpleNamespace(
                current_behavior_snapshot=lambda: behavior_snapshot
            )
        },
    )

    def _randomize() -> SeedRandomizationResult:
        """Record one explicit post-capture rearm."""

        nonlocal randomizer_calls
        randomizer_calls += 1
        return SeedRandomizationResult()

    bindings = cast(
        Any,
        build_generation_action_bindings(
            view=cast(GenerationActionBindingView, view),
            build_generation_request=lambda: request,
            randomize_generation_seeds=_randomize,
            build_queued_generation_snapshots=lambda: (),
            capture_queued_generation_preparation=lambda: cast(
                QueuedGenerationPreparationJob, object()
            ),
        ),
    )

    assert bindings.build_generation_request() is request
    assert randomizer_calls == 0
    bindings.randomize_seeds()
    assert randomizer_calls == 1
    assert bindings.on_run_started is dispatcher.on_run_started
    assert bindings.on_progress is dispatcher.on_progress
    assert bindings.on_model_load_progress is dispatcher.on_model_load_progress
    assert bindings.on_preview is dispatcher.on_preview
    assert bindings.on_output_image is dispatcher.on_output_image
    assert bindings.on_failure is dispatcher.on_failure
    assert bindings.on_timing is dispatcher.on_timing
    assert bindings.on_completed is dispatcher.on_completed
    assert bindings.build_queued_generation_snapshots() == ()


def test_locking_after_generation_reuses_the_submitted_seed() -> None:
    """Locking a random seed should preserve the seed submitted by the prior run."""

    workflow = WorkflowState(global_overrides={"seed": {"value": 7, "mode": "global"}})
    seed_values = iter((41, 99))
    seed_randomization_service = SeedRandomizationService()
    view = SimpleNamespace(
        generation_feedback_dispatcher=_dispatcher(),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        editor_panels={},
    )

    def _build_request() -> GenerationRequest:
        """Build a request over the authoritative live workflow."""

        seed_value = workflow.global_overrides["seed"]["value"]
        return GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(Any, deepcopy(workflow)),
            global_override_scopes={
                "seed": GlobalOverrideScope(
                    override_key="seed",
                    value=seed_value,
                    mode="global",
                    full_participation=True,
                    participant_fields=frozenset({("Demo", "KSampler", "seed")}),
                )
            },
        )

    def _randomize() -> SeedRandomizationResult:
        """Rearm the authoritative workflow through deterministic seed policy."""

        return seed_randomization_service.randomize_workflow_seeds(
            workflow=workflow,
            behavior_snapshot=None,
            randint=lambda _lower, _upper: next(seed_values),
        )

    bindings = cast(
        Any,
        build_generation_action_bindings(
            view=cast(GenerationActionBindingView, view),
            build_generation_request=_build_request,
            randomize_generation_seeds=_randomize,
            build_queued_generation_snapshots=lambda: (),
            capture_queued_generation_preparation=lambda: cast(
                QueuedGenerationPreparationJob, object()
            ),
        ),
    )

    first_request = bindings.build_generation_request()
    first_submitted_seed = first_request.workflow.global_overrides["seed"]["value"]
    assert first_request.global_override_scopes is not None
    first_scope_seed = first_request.global_override_scopes["seed"].value
    bindings.randomize_seeds()
    workflow.override_control_states["seed"] = SeedControlState(SeedMode.FIXED)
    second_request = bindings.build_generation_request()

    assert first_submitted_seed == 7
    assert first_scope_seed == 7
    assert second_request.global_override_scopes is not None
    assert second_request.workflow.global_overrides["seed"]["value"] == 41
    assert second_request.global_override_scopes["seed"].value == 41
