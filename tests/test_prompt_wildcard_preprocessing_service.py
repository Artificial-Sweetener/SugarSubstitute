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

"""Tests for generation-time prompt wildcard preprocessing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from substitute.application.prompt_wildcards import (
    PromptWildcardPreprocessingContext,
    PromptWildcardPreprocessingService,
    PromptWildcardResolutionContext,
    PromptWildcardSeedSelection,
)
from substitute.application.prompt_wildcards.resolver import PromptWildcardResolver
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.domain.prompt import PromptWildcardCsvSource, PromptWildcardTextSource
from substitute.infrastructure.persistence.file_prompt_wildcard_catalog_gateway import (
    FilePromptWildcardCatalogGateway,
)


def _write_text(path: Path, content: str) -> None:
    """Write one UTF-8 test fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _gateway(user_root: Path) -> FilePromptWildcardCatalogGateway:
    """Build one wildcard source gateway for tests."""

    return FilePromptWildcardCatalogGateway(
        user_wildcards_root=user_root,
        comfy_custom_nodes_root=user_root.parent / "comfy_custom_nodes",
    )


def _workflow() -> SimpleNamespace:
    """Build a minimal workflow containing one wildcard prompt cube."""

    cube = SimpleNamespace(
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
        buffer={
            "nodes": {
                "ksampler": {"class_type": "KSampler", "inputs": {"seed": 123}},
                "positive_prompt": {
                    "class_type": "CSVWildcardNode",
                    "inputs": {
                        "prompt_template": "A {animal}",
                        "seed": 999,
                    },
                },
            }
        },
    )
    return SimpleNamespace(
        stack_order=["Text"],
        cubes={"Text": cube},
        global_overrides={},
    )


def _multi_prompt_workflow() -> SimpleNamespace:
    """Build a workflow with multiple wildcard prompt fields sharing one seed."""

    cube = SimpleNamespace(
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
        buffer={
            "nodes": {
                "ksampler": {"class_type": "KSampler", "inputs": {"seed": 1}},
                "positive_prompt": {
                    "class_type": "CSVWildcardNode",
                    "inputs": {"prompt_template": "A {color} {animal}"},
                },
                "negative_prompt": {
                    "class_type": "CSVWildcardNode",
                    "inputs": {"prompt_template": "avoid {animal}"},
                },
            }
        },
    )
    return SimpleNamespace(
        stack_order=["Text"],
        cubes={"Text": cube},
        global_overrides={},
    )


def _single_prompt_workflow(prompt_text: str) -> SimpleNamespace:
    """Build a one-prompt workflow with a fixed seed control."""

    cube = SimpleNamespace(
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
        buffer={
            "nodes": {
                "ksampler": {"class_type": "KSampler", "inputs": {"seed": 1}},
                "positive_prompt": {
                    "class_type": "CSVWildcardNode",
                    "inputs": {"prompt_template": prompt_text},
                },
            }
        },
    )
    return SimpleNamespace(
        stack_order=["Text"],
        cubes={"Text": cube},
        global_overrides={},
    )


class _CountingSourceProvider:
    """Return deterministic wildcard sources while recording load calls."""

    def __init__(self) -> None:
        """Initialize source load counters."""

        self.text_calls: list[str] = []
        self.csv_calls: list[str] = []

    def load_text_source(self, identifier: str) -> PromptWildcardTextSource | None:
        """Return a fixed source for simple wildcard placeholders."""

        self.text_calls.append(identifier)
        if identifier == "animal":
            return PromptWildcardTextSource(
                source_id="animal",
                lines=("wolf", "bear", "fox"),
            )
        return None

    def load_csv_source(self, identifier: str) -> PromptWildcardCsvSource | None:
        """Return no CSV sources for these tests."""

        self.csv_calls.append(identifier)
        return None


class _CountingSeedPolicy:
    """Return a fixed seed while recording selection calls."""

    def __init__(self) -> None:
        """Initialize seed selection counters."""

        self.calls: list[tuple[str, str, str]] = []

    def select_seed(
        self,
        *,
        workflow: object,
        prompt_cube_alias: str,
        workflow_id: str,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptWildcardSeedSelection:
        """Return a deterministic seed for the requested prompt field."""

        _ = workflow, workflow_id
        self.calls.append((prompt_cube_alias, prompt_node_name, prompt_field_key))
        return PromptWildcardSeedSelection(seed=1)


def test_preprocessing_resolves_prompt_copy_without_mutating_live_workflow(
    tmp_path: Path,
) -> None:
    """Generation preprocessing should resolve only a copied workflow state."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    workflow = _workflow()
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))

    resolved = service.preprocess_workflow(workflow=workflow, workflow_id="wf")

    live_prompt = workflow.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "prompt_template"
    ]
    resolved_prompt = resolved.cubes["Text"].buffer["nodes"]["positive_prompt"][
        "inputs"
    ]["prompt_template"]
    assert live_prompt == "A {animal}"
    assert resolved_prompt == "A wolf"


def test_preprocessing_in_place_resolves_owned_workflow_copy(tmp_path: Path) -> None:
    """The explicit in-place path should mutate the supplied generation workflow."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    workflow = _workflow()
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))

    service.preprocess_workflow_in_place(workflow=workflow, workflow_id="wf")

    assert (
        workflow.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
            "prompt_template"
        ]
        == "A wolf"
    )


def test_preprocessing_context_shares_wildcard_choices_across_prompt_fields(
    tmp_path: Path,
) -> None:
    """Shared preprocessing context should stabilize repeated sources by pass seed."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "color.txt", "red\ngreen\nblue\n")
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    workflow = _multi_prompt_workflow()
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))
    context = PromptWildcardResolutionContext()

    resolved = service.preprocess_workflow(
        workflow=workflow,
        workflow_id="wf",
        wildcard_context=context,
    )

    nodes = resolved.cubes["Text"].buffer["nodes"]
    positive = nodes["positive_prompt"]["inputs"]["prompt_template"]
    negative = nodes["negative_prompt"]["inputs"]["prompt_template"]
    animal = positive.rsplit(" ", 1)[1]
    assert negative == f"avoid {animal}"


def test_preprocessing_uses_shared_context_by_default(tmp_path: Path) -> None:
    """One workflow pass should stabilize repeated sources without caller context."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "color.txt", "red\ngreen\nblue\n")
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    workflow = _multi_prompt_workflow()
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))

    resolved = service.preprocess_workflow(
        workflow=workflow,
        workflow_id="wf",
    )

    nodes = resolved.cubes["Text"].buffer["nodes"]
    positive = nodes["positive_prompt"]["inputs"]["prompt_template"]
    negative = nodes["negative_prompt"]["inputs"]["prompt_template"]
    animal = positive.rsplit(" ", 1)[1]
    assert negative == f"avoid {animal}"


def test_preprocessing_context_shares_wildcard_choices_across_scene_workflows(
    tmp_path: Path,
) -> None:
    """One pass context should keep source selections stable across scene copies."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "color.txt", "red\ngreen\nblue\n")
    _write_text(user_root / "animal.txt", "wolf\nbear\nfox\n")
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))
    context = PromptWildcardResolutionContext()

    first = service.preprocess_workflow(
        workflow=_single_prompt_workflow("scene one {color} {animal}"),
        workflow_id="wf",
        wildcard_context=context,
    )
    second = service.preprocess_workflow(
        workflow=_single_prompt_workflow("scene two {animal}"),
        workflow_id="wf",
        wildcard_context=context,
    )

    first_prompt = first.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "prompt_template"
    ]
    second_prompt = second.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "prompt_template"
    ]
    animal = first_prompt.rsplit(" ", 1)[1]
    assert second_prompt == f"scene two {animal}"


def test_preprocessing_context_caches_exact_prompt_resolution(
    monkeypatch: Any,
) -> None:
    """Repeated exact prompt text should resolve once per request context."""

    source_provider = _CountingSourceProvider()
    seed_policy = _CountingSeedPolicy()
    service = PromptWildcardPreprocessingService(
        source_provider=source_provider,
        seed_policy=seed_policy,  # type: ignore[arg-type]
    )
    preprocessing_context = PromptWildcardPreprocessingContext()
    original_resolve = PromptWildcardResolver.resolve
    resolve_calls: list[str] = []

    def _counting_resolve(
        self: object,
        prompt_text: str,
        *,
        seed: int | None = None,
        context: PromptWildcardResolutionContext | None = None,
    ) -> object:
        """Count resolver calls while delegating to the real resolver."""

        resolve_calls.append(prompt_text)
        return original_resolve(self, prompt_text, seed=seed, context=context)  # type: ignore[arg-type]

    monkeypatch.setattr(PromptWildcardResolver, "resolve", _counting_resolve)

    first = service.preprocess_workflow(
        workflow=_single_prompt_workflow("A {animal}"),
        workflow_id="wf",
        preprocessing_context=preprocessing_context,
    )
    second = service.preprocess_workflow(
        workflow=_single_prompt_workflow("A {animal}"),
        workflow_id="wf",
        preprocessing_context=preprocessing_context,
    )

    first_prompt = first.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "prompt_template"
    ]
    second_prompt = second.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "prompt_template"
    ]
    assert first_prompt == second_prompt
    assert resolve_calls == ["A {animal}"]
    assert source_provider.text_calls == ["animal"]
    assert seed_policy.calls == [("Text", "positive_prompt", "prompt_template")]


def test_resolver_records_wildcard_replacement_provenance() -> None:
    """Wildcard resolution should retain selected source metadata for tracing."""

    source_provider = _CountingSourceProvider()
    resolver = PromptWildcardResolver(source_provider)

    resolution = resolver.resolve(
        "A {animal}",
        seed=1,
        context=PromptWildcardResolutionContext(),
    )

    assert resolution.replacements == (("{animal}", "wolf"),)
    assert len(resolution.replacement_details) == 1
    detail = resolution.replacement_details[0]
    assert detail.outer_text == "{animal}"
    assert detail.value == "wolf"
    assert detail.identifier == "animal"
    assert detail.source_id == "animal"
    assert detail.selected_index == 0
    assert detail.line_number == 1
    assert detail.item_count == 3
    assert detail.seed == 1


def test_resolve_workflow_prompt_field_overrides_preserves_live_workflow() -> None:
    """Overlay wildcard resolution should return prompt overrides without mutation."""

    source_provider = _CountingSourceProvider()
    service = PromptWildcardPreprocessingService(source_provider=source_provider)
    workflow = _single_prompt_workflow("base {animal}")

    overrides = service.resolve_workflow_prompt_field_overrides(
        workflow=workflow,
        workflow_id="wf",
        prompt_field_overrides={
            ("Text", "positive_prompt", "prompt_template"): "scene {animal}",
        },
    )

    assert overrides[("Text", "positive_prompt", "prompt_template")].startswith(
        "scene "
    )
    assert (
        workflow.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
            "prompt_template"
        ]
        == "base {animal}"
    )


def test_preprocessing_resolves_semantic_prompt_endpoint_class(
    tmp_path: Path,
) -> None:
    """Prompt endpoint metadata should resolve custom prompt node fields."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    cube = SimpleNamespace(
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
        buffer={
            "nodes": {
                "ksampler": {"class_type": "KSampler", "inputs": {"seed": 1}},
                "custom_prompt": {
                    "class_type": "CustomPromptNode",
                    "inputs": {"text": "A {animal}"},
                },
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["Text"],
        cubes={"Text": cube},
        global_overrides={},
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="custom_prompt",
                field_key="text",
            ),
        )
    )
    service = PromptWildcardPreprocessingService(source_provider=_gateway(user_root))

    resolved = service.preprocess_workflow(
        workflow=workflow,
        workflow_id="wf",
        prompt_endpoint_index=endpoint_index,
    )

    assert (
        resolved.cubes["Text"].buffer["nodes"]["custom_prompt"]["inputs"]["text"]
        == "A wolf"
    )


def test_preprocessing_can_be_disabled(tmp_path: Path) -> None:
    """Disabled generation preprocessing should return an unresolved copy."""

    user_root = tmp_path / "user" / "wildcards"
    _write_text(user_root / "animal.txt", "wolf\n")
    service = PromptWildcardPreprocessingService(
        source_provider=_gateway(user_root),
        resolve_on_generation=False,
    )

    resolved = service.preprocess_workflow(workflow=_workflow(), workflow_id="wf")

    assert (
        resolved.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
            "prompt_template"
        ]
        == "A {animal}"
    )
