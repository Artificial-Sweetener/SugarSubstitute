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
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.generation import (
    GenerationRequest,
    SeedRandomizationResult,
    SeedRandomizationService,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.presentation.shell.workspace_generation_action_adapter import (
    effective_generation_batch_count,
    randomize_generation_request_seeds,
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


def test_effective_generation_batch_count_prefers_registry_and_clamps() -> None:
    """Titlebar registry batch count should win over legacy cluster values."""

    view = SimpleNamespace(
        generation_titlebar_control_registry=SimpleNamespace(
            effective_batch_count=lambda: 0
        ),
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 7),
    )

    assert effective_generation_batch_count(view) == 1


def test_effective_generation_batch_count_uses_legacy_cluster_fallback() -> None:
    """Legacy generation action cluster should supply batch count when needed."""

    view = SimpleNamespace(
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 4)
    )

    assert effective_generation_batch_count(view) == 4
    assert effective_generation_batch_count(SimpleNamespace()) == 1


def test_randomize_generation_request_seeds_delegates_to_service() -> None:
    """Seed randomization should delegate workflow mutation to the service port."""

    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    workflow = SimpleNamespace()
    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, workflow),
    )
    calls: list[tuple[object, EditorBehaviorSnapshot | None]] = []

    class _SeedRandomizer:
        """Record seed randomization calls."""

        def randomize_workflow_seeds(
            self,
            *,
            workflow: object,
            behavior_snapshot: EditorBehaviorSnapshot | None,
        ) -> SeedRandomizationResult:
            """Record request workflow and behavior snapshot."""

            calls.append((workflow, behavior_snapshot))
            return SeedRandomizationResult()

    randomize_generation_request_seeds(
        seed_randomization_service=_SeedRandomizer(),
        request=request,
        behavior_snapshot=behavior_snapshot,
    )

    assert calls == [(workflow, behavior_snapshot)]


def test_randomize_generation_request_seeds_skips_plain_workflow_for_concrete_service() -> (
    None
):
    """Concrete seed randomizer should ignore plain non-WorkflowState requests."""

    request = GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(Any, SimpleNamespace()),
    )

    randomize_generation_request_seeds(
        seed_randomization_service=SeedRandomizationService(),
        request=request,
        behavior_snapshot=None,
    )
