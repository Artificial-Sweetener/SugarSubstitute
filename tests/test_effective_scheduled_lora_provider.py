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

"""Contract tests for effective scheduled LoRA prompt-context resolution."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelChoiceCatalogIndex,
    RichChoiceResolver,
)
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    ResolvedFieldSpec,
)
from substitute.application.prompt_editor import (
    EffectiveScheduledLoraProvider,
    PromptLoraCatalogItem,
    PromptScheduledLoraService,
    WorkflowPromptContext,
)


class _StaticNodeDefinitionGateway:
    """Return deterministic live node definitions."""

    def __init__(self, definitions_by_class: Mapping[str, dict[str, Any]]) -> None:
        """Store node definitions keyed by class type."""

        self._definitions_by_class = dict(definitions_by_class)
        self.calls = 0

    def get_node_definition(self, node_class: str) -> dict[str, Any]:
        """Return the definition for one node class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, Any]:
        """Return the required definition for one node class."""

        self.calls += 1
        return {node_class: self._definitions_by_class.get(node_class, {})}


class _StaticModelCatalog:
    """Return deterministic model catalog rows."""

    def __init__(
        self, items_by_kind: Mapping[str, tuple[ModelCatalogItem, ...]]
    ) -> None:
        """Store model rows keyed by kind."""

        self._items_by_kind = dict(items_by_kind)

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured model rows for one kind."""

        return self._items_by_kind.get(kind, ())

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured model rows for refresh calls."""

        return self.list_models(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Satisfy the model catalog protocol without mutable cache state."""

        _ = kind


class _StaticPromptLoraCatalog:
    """Return deterministic prompt LoRA catalog rows."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store prompt LoRA rows."""

        self._items = items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured prompt LoRA rows."""

        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured prompt LoRA rows without backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return a prompt LoRA row matching prompt or backend value."""

        normalized = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized:
                return item
            if item.backend_value.replace("\\", "/").casefold() == normalized:
                return item
        return None


class _StaticRecipeIoService:
    """Return deterministic Sugar script text for graph tests."""

    def __init__(self, text: str) -> None:
        """Store serialized script text."""

        self._text = text
        self.calls = 0

    def serialize_workflow_to_sugar_script(self, workflow: object) -> str:
        """Return configured script text after touching the workflow shape."""

        self.calls += 1
        assert hasattr(workflow, "stack_order")
        assert hasattr(workflow, "cubes")
        assert hasattr(workflow, "global_overrides")
        return self._text


class _StaticWorkflowExportService:
    """Return deterministic compiled workflow payloads."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Store compiled payload."""

        self.calls = 0
        self._payload = payload

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: object,
    ) -> dict[str, Any]:
        """Return configured graph payload and record compilation."""

        _ = (sugar_script_text, output_dir)
        self.calls += 1
        return self._payload


def _model_item(
    *,
    kind: str = "loras",
    backend_value: str = "characters/midna.safetensors",
    display_name: str = "CivitAI Midna",
    trained_words: tuple[str, ...] = ("imp princess",),
) -> ModelCatalogItem:
    """Return one deterministic model catalog row."""

    basename = backend_value.replace("\\", "/").rsplit("/", 1)[-1]
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder=backend_value.rsplit("/", 1)[0] if "/" in backend_value else "",
        basename=basename.removesuffix(".safetensors"),
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=trained_words,
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, backend_value)).casefold(),
    )


def _prompt_lora_item(
    *,
    backend_value: str = "characters/midna.safetensors",
    prompt_name: str = "characters/midna",
    display_name: str = "CivitAI Midna",
    trained_words: tuple[str, ...] = ("imp princess",),
) -> PromptLoraCatalogItem:
    """Return one deterministic prompt LoRA catalog row."""

    basename = backend_value.replace("\\", "/").rsplit("/", 1)[-1]
    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=backend_value,
        relative_path=backend_value,
        folder=backend_value.rsplit("/", 1)[0] if "/" in backend_value else "",
        basename=basename.removesuffix(".safetensors"),
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=trained_words,
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, backend_value)).casefold(),
    )


def _provider(
    *,
    model_items: tuple[ModelCatalogItem, ...],
    prompt_lora_items: tuple[PromptLoraCatalogItem, ...],
    workflow_payload: dict[str, Any] | None = None,
    definitions_by_class: Mapping[str, dict[str, Any]] | None = None,
) -> tuple[EffectiveScheduledLoraProvider, _StaticWorkflowExportService]:
    """Return a provider with deterministic collaborators."""

    export_service = _StaticWorkflowExportService(workflow_payload or {})
    live_definitions = definitions_by_class
    if live_definitions is None:
        live_definitions = {
            "LoRASchedule": {
                "input": {
                    "required": {
                        "lora_name": [[item.backend_value for item in model_items]]
                    }
                }
            }
        }
    provider = EffectiveScheduledLoraProvider(
        recipe_io_service=_StaticRecipeIoService("stack script"),
        workflow_export_service=export_service,
        prompt_scheduled_lora_service=PromptScheduledLoraService(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog(prompt_lora_items),
        rich_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(
                model_catalog=_StaticModelCatalog({"loras": model_items})
            )
        ),
        node_definition_gateway=_StaticNodeDefinitionGateway(live_definitions),
        output_dir=Path("."),
    )
    return provider, export_service


def _field_spec(value: str, *, field_key: str = "lora_name") -> ResolvedFieldSpec:
    """Return a LIST field spec for one LoRA schedule field."""

    return ResolvedFieldSpec(
        cube_alias="Cube",
        node_name="schedule_lora",
        class_type="LoRASchedule",
        field_key=field_key,
        field_type="LIST",
        constraints={},
        meta_info={},
        field_info=None,
        value=value,
        field_behavior=FieldBehavior(field_key=field_key),
    )


def _workflow_context(
    snapshot: EditorBehaviorSnapshot | None,
    *,
    cache_token: tuple[str, ...] = (),
) -> WorkflowPromptContext:
    """Return one minimal workflow prompt context."""

    return WorkflowPromptContext(
        cube_states={"Cube": SimpleNamespace(cube_id="text_to_image", buffer={})},
        stack_order=("Cube",),
        workflow_overrides={},
        behavior_snapshot=snapshot,
        cache_token=cache_token,
    )


def test_effective_provider_resolves_enriched_lora_list_fields() -> None:
    """Enriched LoRA LIST fields in the prompt cube should become scheduled LoRAs."""

    model_item = _model_item()
    prompt_item = _prompt_lora_item()
    snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "Cube": {
                "schedule_lora": {"lora_name": _field_spec(model_item.backend_value)}
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    provider, _export_service = _provider(
        model_items=(model_item,),
        prompt_lora_items=(prompt_item,),
    )

    scheduled_loras = provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(snapshot),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )

    assert [
        (lora.backend_value, lora.display_name, lora.trained_words, lora.source)
        for lora in scheduled_loras
    ] == [
        (
            "characters/midna.safetensors",
            "CivitAI Midna",
            ("imp princess",),
            "cube_field",
        )
    ]


def test_effective_provider_ignores_checkpoint_and_vae_list_fields() -> None:
    """Only LIST fields enriched as LoRAs should create scheduled LoRA rows."""

    checkpoint_item = _model_item(
        kind="checkpoints",
        backend_value="dream.safetensors",
        display_name="Dream Checkpoint",
    )
    snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "Cube": {"checkpoint": {"ckpt_name": _field_spec("dream.safetensors")}}
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    provider, _export_service = _provider(
        model_items=(checkpoint_item,),
        prompt_lora_items=(),
    )

    scheduled_loras = provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(snapshot),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )

    assert scheduled_loras == ()


def test_effective_provider_ignores_compact_dynamic_list_without_live_options() -> None:
    """Compact dynamic LIST markers should not enrich LoRAs without live choices."""

    model_item = _model_item()
    snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "Cube": {
                "schedule_lora": {
                    "lora_name": ResolvedFieldSpec(
                        cube_alias="Cube",
                        node_name="schedule_lora",
                        class_type="LoRASchedule",
                        field_key="lora_name",
                        field_type="LIST",
                        constraints={},
                        meta_info={},
                        field_info=["LIST", {"dynamic": True}],
                        value=model_item.backend_value,
                        field_behavior=FieldBehavior(field_key="lora_name"),
                    )
                }
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    provider, _export_service = _provider(
        model_items=(model_item,),
        prompt_lora_items=(_prompt_lora_item(),),
        definitions_by_class={
            "LoRASchedule": {
                "input": {"required": {"lora_name": ["LIST", {"dynamic": True}]}}
            }
        },
    )

    scheduled_loras = provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(snapshot),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )

    assert scheduled_loras == ()


def test_effective_provider_collects_graph_effective_loras_for_prompt_branch() -> None:
    """Compiled graph LoRA nodes feeding the prompt branch should count as scheduled."""

    prompt_item = _prompt_lora_item()
    workflow_payload: dict[str, Any] = {
        "prompt": {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {},
                "_meta": {"title": "Base.checkpoint"},
            },
            "2": {
                "class_type": "PCLazyLoraLoader",
                "inputs": {
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "lora_name": prompt_item.backend_value,
                },
                "_meta": {"title": "Cube.schedule_lora"},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 1], "text": "portrait"},
                "_meta": {"title": "Cube.prompt"},
            },
        },
        "workflow": {"nodes": []},
    }
    provider, export_service = _provider(
        model_items=(),
        prompt_lora_items=(prompt_item,),
        workflow_payload=workflow_payload,
    )

    scheduled_loras = provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(None),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )
    scheduled_again = provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(None),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait in profile",
    )

    assert [(lora.backend_value, lora.source) for lora in scheduled_loras] == [
        ("characters/midna.safetensors", "graph_effective")
    ]
    assert scheduled_again == scheduled_loras
    assert export_service.calls == 1


def test_effective_provider_reuses_context_cache_for_graph_loras() -> None:
    """Context-token graph cache should avoid repeated workflow serialization."""

    prompt_item = _prompt_lora_item()
    workflow_payload: dict[str, Any] = {
        "2": {
            "class_type": "PCLazyLoraLoader",
            "inputs": {"lora_name": prompt_item.backend_value},
            "_meta": {"title": "Cube.schedule_lora"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 1], "text": "portrait"},
            "_meta": {"title": "Cube.prompt"},
        },
    }
    recipe_service = _StaticRecipeIoService("stack script")
    export_service = _StaticWorkflowExportService(workflow_payload)
    provider = EffectiveScheduledLoraProvider(
        recipe_io_service=recipe_service,
        workflow_export_service=export_service,
        prompt_scheduled_lora_service=PromptScheduledLoraService(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog((prompt_item,)),
        rich_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(
                model_catalog=_StaticModelCatalog({"loras": ()})
            )
        ),
        node_definition_gateway=_StaticNodeDefinitionGateway({}),
        output_dir=Path("."),
    )
    context = _workflow_context(None, cache_token=("workflow", "one"))

    first = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )
    second = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait closeup",
    )

    assert second == first
    assert recipe_service.calls == 1
    assert export_service.calls == 1


def test_effective_provider_reuses_compiled_payload_for_distinct_prompt_fields() -> (
    None
):
    """One Sugar script should compile once across prompt-field graph analysis."""

    prompt_item = _prompt_lora_item()
    workflow_payload: dict[str, Any] = {
        "2": {
            "class_type": "PCLazyLoraLoader",
            "inputs": {"lora_name": prompt_item.backend_value},
            "_meta": {"title": "Cube.schedule_lora"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 1], "text": "portrait"},
            "_meta": {"title": "Cube.positive_prompt"},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 1], "text": "background"},
            "_meta": {"title": "Cube.negative_prompt"},
        },
    }
    recipe_service = _StaticRecipeIoService("stack script")
    export_service = _StaticWorkflowExportService(workflow_payload)
    provider = EffectiveScheduledLoraProvider(
        recipe_io_service=recipe_service,
        workflow_export_service=export_service,
        prompt_scheduled_lora_service=PromptScheduledLoraService(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog((prompt_item,)),
        rich_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(
                model_catalog=_StaticModelCatalog({"loras": ()})
            )
        ),
        node_definition_gateway=_StaticNodeDefinitionGateway({}),
        output_dir=Path("."),
    )
    context = _workflow_context(None, cache_token=("workflow", "one"))

    positive = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="positive_prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )
    negative = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="negative_prompt",
        prompt_field_key="text",
        prompt_text="background",
    )

    assert [(lora.backend_value, lora.source) for lora in positive] == [
        ("characters/midna.safetensors", "graph_effective")
    ]
    assert negative == positive
    assert recipe_service.calls == 2
    assert export_service.calls == 1


def test_effective_provider_invalidates_context_cache_when_token_changes() -> None:
    """Changing workflow context tokens should recompute graph-effective LoRAs."""

    prompt_item = _prompt_lora_item()
    workflow_payload: dict[str, Any] = {
        "2": {
            "class_type": "PCLazyLoraLoader",
            "inputs": {"lora_name": prompt_item.backend_value},
            "_meta": {"title": "Cube.schedule_lora"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 1], "text": "portrait"},
            "_meta": {"title": "Cube.prompt"},
        },
    }
    recipe_service = _StaticRecipeIoService("stack script")
    export_service = _StaticWorkflowExportService(workflow_payload)
    provider = EffectiveScheduledLoraProvider(
        recipe_io_service=recipe_service,
        workflow_export_service=export_service,
        prompt_scheduled_lora_service=PromptScheduledLoraService(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog((prompt_item,)),
        rich_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(
                model_catalog=_StaticModelCatalog({"loras": ()})
            )
        ),
        node_definition_gateway=_StaticNodeDefinitionGateway({}),
        output_dir=Path("."),
    )

    provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(None, cache_token=("workflow", "one")),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )
    provider.scheduled_loras_for_prompt_context(
        workflow_context=_workflow_context(None, cache_token=("workflow", "two")),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )

    assert recipe_service.calls == 2
    assert export_service.calls == 1


def test_effective_provider_reuses_context_cache_for_cube_field_loras() -> None:
    """Context-token cube cache should avoid repeated live LIST resolution."""

    model_item = _model_item()
    prompt_item = _prompt_lora_item()
    snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={
            "Cube": {
                "schedule_lora": {"lora_name": _field_spec(model_item.backend_value)}
            }
        },
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
    node_gateway = _StaticNodeDefinitionGateway(
        {
            "LoRASchedule": {
                "input": {"required": {"lora_name": [[model_item.backend_value]]}}
            }
        }
    )
    provider = EffectiveScheduledLoraProvider(
        recipe_io_service=_StaticRecipeIoService("stack script"),
        workflow_export_service=_StaticWorkflowExportService({}),
        prompt_scheduled_lora_service=PromptScheduledLoraService(),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog((prompt_item,)),
        rich_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(
                model_catalog=_StaticModelCatalog({"loras": (model_item,)})
            )
        ),
        node_definition_gateway=node_gateway,
        output_dir=Path("."),
    )
    context = _workflow_context(snapshot, cache_token=("workflow", "one"))

    first = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait",
    )
    second = provider.scheduled_loras_for_prompt_context(
        workflow_context=context,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
        prompt_text="portrait closeup",
    )

    assert second == first
    assert node_gateway.calls == 1
