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

"""Exercise workflow seed randomization through wildcard generation preparation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import random
from typing import Any, cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationPreparationService,
    GenerationRequest,
)
from substitute.application.generation.seed_randomization_service import (
    SeedRandomizationService,
)
from substitute.application.prompt_wildcards import PromptWildcardPreprocessingService
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
    FilePromptWildcardCatalogGateway,
)

_CANDIDATES = ("first", "second", "third")
_PROMPT_LOCATOR = ("Text", "positive_prompt", "text")


@dataclass(frozen=True, slots=True)
class WildcardGenerationObservation:
    """Capture one randomized workflow seed and its prepared prompt."""

    requested_seed: int
    effective_seed: int
    expected_prompt: str
    prepared_prompt: str

    @property
    def passed(self) -> bool:
        """Return whether generation used the randomized effective seed."""

        return (
            self.effective_seed == self.requested_seed
            and self.prepared_prompt == self.expected_prompt
        )


@dataclass(frozen=True, slots=True)
class WildcardGenerationHarnessReport:
    """Summarize effective-seed wildcard behavior across generation requests."""

    observations: tuple[WildcardGenerationObservation, ...]

    @property
    def passed(self) -> bool:
        """Return whether seeds controlled resolution and produced variation."""

        prepared_prompts = {
            observation.prepared_prompt for observation in self.observations
        }
        return (
            all(observation.passed for observation in self.observations)
            and len(prepared_prompts) > 1
        )

    def failure_summary(self) -> str:
        """Return assertion-ready evidence for all generation observations."""

        return "; ".join(
            (
                f"seed {observation.requested_seed}: expected "
                f"{observation.expected_prompt!r}, prepared "
                f"{observation.prepared_prompt!r}, effective seed "
                f"{observation.effective_seed}"
            )
            for observation in self.observations
        )


class HeadlessWildcardGenerationHarness:
    """Drive real seed randomization, wildcard preprocessing, and queue preparation."""

    def __init__(self, workspace_root: Path) -> None:
        """Configure an isolated wildcard catalog and production services."""

        self._wildcards_root = Path(workspace_root) / "user" / "wildcards"
        self._wildcards_root.mkdir(parents=True, exist_ok=True)
        (self._wildcards_root / "subject.txt").write_text(
            "\n".join(_CANDIDATES) + "\n",
            encoding="utf-8",
        )
        self._preprocessor = PromptWildcardPreprocessingService(
            source_provider=FilePromptWildcardCatalogGateway(
                user_wildcards_root=self._wildcards_root,
                comfy_custom_nodes_root=Path(workspace_root) / "comfy" / "custom_nodes",
            )
        )

    def run(
        self, *, seeds: tuple[int, ...] = (1, 5)
    ) -> WildcardGenerationHarnessReport:
        """Prepare one real generation request for each controlled random seed."""

        return WildcardGenerationHarnessReport(
            observations=tuple(self._prepare(seed) for seed in seeds)
        )

    def _prepare(self, seed: int) -> WildcardGenerationObservation:
        """Randomize and prepare one workflow with a stale downstream cube seed."""

        workflow = _workflow()
        SeedRandomizationService().randomize_workflow_seeds(
            workflow=workflow,
            behavior_snapshot=None,
            randint=lambda _minimum, _maximum: seed,
        )
        effective_seed = cast(int, workflow.global_overrides["seed"]["value"])
        captured = CapturedGenerationRequest.capture(
            request=GenerationRequest(
                workflow_id="Scene Test",
                workflow_name="Scene Test",
                workflow=cast(Any, workflow),
            ),
            behavior_snapshot=None,
        )
        result = GenerationPreparationService(
            recipe_io_service=_PromptRecordingSerializer(),
            prompt_wildcard_preprocessing_service=self._preprocessor,
        ).prepare_queued_snapshots(request=captured)
        prepared_prompt = result.snapshots[0].sugar_script_text.removeprefix("prompt=")
        expected_candidate = random.Random(seed).choice(_CANDIDATES)
        return WildcardGenerationObservation(
            requested_seed=seed,
            effective_seed=effective_seed,
            expected_prompt=f"portrait {expected_candidate}",
            prepared_prompt=prepared_prompt,
        )


class _PromptRecordingSerializer:
    """Render the production prompt overlay into an inspectable snapshot string."""

    def create_serialization_context(self) -> object:
        """Return a stable serialization context for queue preparation."""

        return object()

    def build_serialization_plan(
        self,
        workflow: object,
        *,
        enabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] | None = None,
        disabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] | None = None,
        serialization_context: object | None = None,
    ) -> object:
        """Return a stable plan after validating preparation inputs."""

        _ = workflow, enabled_node_keys_by_alias, disabled_node_keys_by_alias
        assert serialization_context is not None
        return object()

    def serialize_workflow_to_sugar_script(
        self,
        workflow: object,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
        serialization_context: object | None = None,
        serialization_plan: object | None = None,
    ) -> str:
        """Return the resolved prompt supplied by production preprocessing."""

        _ = workflow
        assert serialization_context is not None
        assert serialization_plan is not None
        overrides = prompt_field_overrides or {}
        return f"prompt={overrides[_PROMPT_LOCATOR]}"


def _workflow() -> WorkflowState:
    """Build the Scene Test seed topology that exposed the wildcard defect."""

    prompt_cube = CubeState(
        cube_id="Prompt",
        version="1.0.0",
        alias="Text",
        original_cube={"surface": {"controls": []}},
        buffer={
            "nodes": {
                "positive_prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "portrait {subject}"},
                }
            }
        },
    )
    downstream_cube = CubeState(
        cube_id="Upscale",
        version="1.0.0",
        alias="Diffusion Upscale",
        original_cube={
            "surface": {
                "controls": [
                    {
                        "control_id": "ksampler.seed",
                        "symbol": "ksampler",
                        "input_name": "seed",
                    }
                ]
            }
        },
        buffer={"nodes": {"ksampler": {"inputs": {"seed": 1}}}},
    )
    return WorkflowState(
        cubes={"Text": prompt_cube, "Diffusion Upscale": downstream_cube},
        stack_order=["Text", "Diffusion Upscale"],
        global_overrides={"seed": {"value": 0, "mode": "global"}},
    )


__all__ = [
    "HeadlessWildcardGenerationHarness",
    "WildcardGenerationHarnessReport",
    "WildcardGenerationObservation",
]
