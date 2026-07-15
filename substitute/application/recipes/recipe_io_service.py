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

"""Coordinate recipe load/save flows between presentation, domain codec, and repositories."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, cast

from substitute.application.ports.recipe_repository import (
    LoadedRecipeDocument,
    RecipeSourceKind,
    RecipeRepository,
)
from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonValue,
)
from substitute.domain.generation.seed_control import SeedControlState
from substitute.domain.recipes.sugar_ast import (
    GlobalOverrideSerializationScope,
    ParsedSugarScript,
)
from substitute.domain.recipes.sugar_script_parser import parse_sugar_script_document
from substitute.domain.recipes.recipe_buffers import strip_recipe_buffers
from substitute.domain.recipes.sugar_script_serializer import (
    SugarScriptSerializationRequest,
    SugarScriptSerializer,
)
from substitute.application.recipes.required_picker_preflight import (
    prepare_required_picker_buffers,
)
from substitute.application.recipes.sugar_label_resolution import (
    SugarScriptLabelIndex,
    resolve_parsed_script_labels,
)
from substitute.application.model_metadata import model_kind_for_field
from substitute.application.recipes.model_hash_lookup import RecipeModelHashLookup
from substitute.application.recipes.lora_prompt_names import (
    normalized_prompt_lora_name,
    prompt_lora_name_for_backend_value,
)
from substitute.application.recipes.inline_lora_parser import inline_lora_spans
from substitute.application.recipes.prompt_lora_hash_lookup import PromptLoraHashLookup
from substitute.application.recipes.recipe_serialization_context import (
    RecipePromptFieldOverrides,
    RecipeSerializationContext,
    RecipeSerializationPlan,
    buffers_with_prompt_field_overrides,
)
from substitute.shared.util.path_safety import (
    ensure_within_root,
    validate_top_level_name,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info

_LOGGER = get_logger("application.recipes.recipe_io_service")
_LOAD_IMAGE_CLASSES = frozenset({"LoadImage", "LoadImageMask"})


class WorkflowLike(Protocol):
    """Describe workflow state required to serialize/save recipe scripts."""

    stack_order: list[str]
    cubes: Mapping[str, "CubeStateLike"]
    global_overrides: GlobalOverrideMap
    global_override_selections: GlobalOverrideSelectionMap
    override_control_states: Mapping[str, SeedControlState]


class CubeStateLike(Protocol):
    """Describe cube state shape required by recipe serialization helpers."""

    cube_id: str
    version: str
    buffer: Mapping[str, JsonValue]
    field_control_states: Mapping[str, Mapping[str, SeedControlState]]


class CubeDefinitionProvider(Protocol):
    """Load cube definitions for SugarScript label resolution during parsing."""

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> Any:
        """Load the active definition for one cube id."""

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> Any:
        """Load a pinned definition version for one cube id."""


@dataclass(frozen=True)
class ParsedRecipeDocument:
    """Capture loaded recipe source metadata and parsed script payload."""

    loaded_document: LoadedRecipeDocument
    parsed_script: ParsedSugarScript


@dataclass(frozen=True)
class RecipeDocumentClassification:
    """Describe whether a path can be loaded as a Sugar recipe document."""

    supported: bool
    source_kind: RecipeSourceKind | None
    reason: str


@dataclass(frozen=True, slots=True)
class _PromptLoraNameReplacement:
    """Describe one inline LoRA prompt-name rewrite by source offsets."""

    start: int
    end: int
    value: str


class RecipeIoService:
    """Own deterministic use-cases for Sugar recipe serialization and persistence."""

    def __init__(
        self,
        recipe_repository: RecipeRepository,
        node_definition_gateway: NodeDefinitionGateway | None = None,
        cube_definition_provider: CubeDefinitionProvider | None = None,
        model_hash_lookup: RecipeModelHashLookup | None = None,
        prompt_lora_hash_lookup: PromptLoraHashLookup | None = None,
        sugar_script_serializer: SugarScriptSerializer | None = None,
    ) -> None:
        """Create service with an injected recipe repository port implementation."""

        self._recipe_repository: RecipeRepository = recipe_repository
        self._node_definition_gateway = node_definition_gateway
        self._cube_definition_provider = cube_definition_provider
        self._model_hash_lookup = model_hash_lookup
        self._prompt_lora_hash_lookup = prompt_lora_hash_lookup
        self._sugar_script_serializer = (
            sugar_script_serializer or SugarScriptSerializer()
        )

    def serialize_workflow_to_sugar_script(
        self,
        workflow: WorkflowLike,
        *,
        enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
        disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
        global_override_scopes: Mapping[str, GlobalOverrideSerializationScope]
        | None = None,
        serialization_context: RecipeSerializationContext | None = None,
        serialization_plan: RecipeSerializationPlan | None = None,
        prompt_field_overrides: RecipePromptFieldOverrides | None = None,
    ) -> str:
        """Serialize workflow cubes and overrides into Sugar script text."""

        plan = serialization_plan or self.build_serialization_plan(
            workflow,
            enabled_node_keys_by_alias=enabled_node_keys_by_alias,
            disabled_node_keys_by_alias=disabled_node_keys_by_alias,
            serialization_context=serialization_context,
        )
        ordered_aliases = list(plan.ordered_aliases)
        prepared_buffers = buffers_with_prompt_field_overrides(
            base_buffers=plan.base_prepared_buffers,
            prompt_field_overrides=prompt_field_overrides,
        )
        canonical_prompt_overrides = self._prompt_lora_canonical_overrides_for_buffers(
            prepared_buffers,
            ordered_aliases,
            serialization_context=serialization_context,
        )
        if canonical_prompt_overrides:
            prepared_buffers = buffers_with_prompt_field_overrides(
                base_buffers=prepared_buffers,
                prompt_field_overrides=canonical_prompt_overrides,
            )
        _log_image_inputs_seen_for_serialization(
            stripped_buffers=prepared_buffers,
            ordered_aliases=ordered_aliases,
        )
        sugar_script = self._sugar_script_serializer.serialize(
            SugarScriptSerializationRequest(
                buffers=prepared_buffers,
                ordered_aliases=tuple(ordered_aliases),
                global_overrides=workflow.global_overrides,
                global_override_selections=getattr(
                    workflow,
                    "global_override_selections",
                    {},
                ),
                field_control_states_by_alias={
                    alias: getattr(cube, "field_control_states", {})
                    for alias, cube in workflow.cubes.items()
                },
                override_control_states=getattr(
                    workflow,
                    "override_control_states",
                    {},
                ),
                enabled_node_keys_by_alias=enabled_node_keys_by_alias,
                disabled_node_keys_by_alias=disabled_node_keys_by_alias,
                global_override_scopes=global_override_scopes,
                label_resolver=plan.label_index,
                model_hashes_by_field=plan.model_hashes_by_field,
                prompt_lora_hashes_by_field=self._prompt_lora_hashes_for_buffers(
                    prepared_buffers,
                    ordered_aliases,
                    serialization_context=serialization_context,
                ),
            )
        )
        return sugar_script

    def create_serialization_context(self) -> RecipeSerializationContext:
        """Create a request-scoped cache context for repeated Sugar serialization."""

        return RecipeSerializationContext(
            model_hash_lookup=_session_model_hash_lookup(self._model_hash_lookup),
            prompt_lora_hash_lookup=_session_prompt_lora_hash_lookup(
                self._prompt_lora_hash_lookup
            ),
        )

    def build_serialization_plan(
        self,
        workflow: WorkflowLike,
        *,
        enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
        disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None,
        serialization_context: RecipeSerializationContext | None = None,
    ) -> RecipeSerializationPlan:
        """Build reusable Sugar serialization inputs for one workflow snapshot."""

        ordered_aliases = tuple(workflow.stack_order)
        ordered_alias_list = list(ordered_aliases)
        stripped_buffers = strip_recipe_buffers(ordered_alias_list, workflow.cubes)
        prepared_buffers = prepare_required_picker_buffers(
            stripped_buffers=stripped_buffers,
            ordered_aliases=ordered_aliases,
            node_definition_gateway=self._node_definition_gateway,
            enabled_node_keys_by_alias=enabled_node_keys_by_alias,
            disabled_node_keys_by_alias=disabled_node_keys_by_alias,
            required_node_definitions_by_class=(
                None
                if serialization_context is None
                else serialization_context.required_node_definitions_by_class
            ),
        )
        label_index = SugarScriptLabelIndex.from_cube_graphs(
            {
                alias: workflow.cubes[alias].buffer
                for alias in ordered_aliases
                if alias in workflow.cubes
            }
        )
        model_hash_lookup = (
            self._model_hash_lookup
            if serialization_context is None
            else serialization_context.model_hash_lookup
        )
        return RecipeSerializationPlan(
            ordered_aliases=ordered_aliases,
            base_stripped_buffers=stripped_buffers,
            base_prepared_buffers=prepared_buffers,
            label_index=label_index,
            model_hashes_by_field=self._model_hashes_for_buffers(
                prepared_buffers,
                ordered_alias_list,
                model_hash_lookup=model_hash_lookup,
            ),
        )

    def save_workflow_recipe(
        self,
        path: Path,
        *,
        workflow_name: str,
        workflow: WorkflowLike,
        global_override_scopes: Mapping[str, GlobalOverrideSerializationScope]
        | None = None,
    ) -> None:
        """Serialize and persist workflow recipe text to destination file path."""

        recipe_text = self.serialize_workflow_to_sugar_script(
            workflow,
            global_override_scopes=global_override_scopes,
        )
        self._recipe_repository.save_recipe_document(
            path,
            project_name=workflow_name,
            sugar_script_text=recipe_text,
        )

    def build_default_recipe_path(
        self, workflow_name: str, sugar_scripts_dir: Path
    ) -> Path:
        """Build the canonical recipe path under the workflow-named script directory."""

        safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
        workflow_dir = ensure_within_root(
            Path(sugar_scripts_dir) / safe_workflow_name,
            root_path=sugar_scripts_dir,
            subject="Workflow directory",
            require_top_level=True,
        )
        return ensure_within_root(
            workflow_dir / f"{safe_workflow_name}.sugar",
            root_path=workflow_dir,
            subject="Workflow recipe",
            require_top_level=True,
        )

    def validate_recipe_destination(self, destination_path: Path) -> Path:
        """Validate a user-selected Sugar recipe destination."""

        return _validate_recipe_destination_path(Path(destination_path))

    def save_workflow_recipe_to_default_path(
        self,
        workflow_name: str,
        workflow: WorkflowLike,
        sugar_scripts_dir: Path,
        *,
        global_override_scopes: Mapping[str, GlobalOverrideSerializationScope]
        | None = None,
    ) -> Path:
        """Save the workflow recipe to its canonical script path and return that path."""

        destination_path = self.build_default_recipe_path(
            workflow_name, sugar_scripts_dir
        )
        self.save_workflow_recipe(
            destination_path,
            workflow_name=validate_top_level_name(workflow_name, subject="Workflow"),
            workflow=workflow,
            global_override_scopes=global_override_scopes,
        )
        return destination_path

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Load recipe script text and source metadata from a filesystem path."""

        log_debug(
            _LOGGER,
            "Recipe IO load requested",
            path=path,
        )
        loaded_document = self._recipe_repository.load_recipe_document(path)
        log_debug(
            _LOGGER,
            "Recipe IO loaded document",
            path=loaded_document.source_path,
            source_kind=loaded_document.source_kind,
            sugar_script_length=len(loaded_document.sugar_script_text),
            sugar_script_sha256=_text_sha256(loaded_document.sugar_script_text),
        )
        return loaded_document

    def classify_recipe_document(self, path: Path) -> RecipeDocumentClassification:
        """Classify a path for cheap recipe-load drag/drop acceptance."""

        source_path = Path(path)
        suffix = source_path.suffix.lower()
        if source_path.is_dir():
            return RecipeDocumentClassification(
                supported=False,
                source_kind=None,
                reason="directory",
            )
        if suffix == ".sugar":
            return RecipeDocumentClassification(
                supported=True,
                source_kind="text",
                reason="text_recipe_extension",
            )
        if suffix == ".png":
            has_embedded_script = self._recipe_repository.has_embedded_recipe_script(
                source_path
            )
            return RecipeDocumentClassification(
                supported=has_embedded_script,
                source_kind="png" if has_embedded_script else None,
                reason="png_embedded_recipe"
                if has_embedded_script
                else "png_without_embedded_recipe",
            )
        return RecipeDocumentClassification(
            supported=False,
            source_kind=None,
            reason="unsupported_extension",
        )

    def can_load_recipe_document(self, path: Path) -> bool:
        """Return whether a path is supported by the recipe document loader."""

        return self.classify_recipe_document(path).supported

    def parse_recipe_script(self, sugar_script_text: str) -> ParsedSugarScript:
        """Parse Sugar script text into ordered cube buffers and overrides."""

        log_info(
            _LOGGER,
            "Recipe IO parse requested",
            sugar_script_length=len(sugar_script_text),
            sugar_script_sha256=_text_sha256(sugar_script_text),
        )
        parsed_script = parse_sugar_script_document(sugar_script_text)
        if self._cube_definition_provider is not None:
            parsed_script = resolve_parsed_script_labels(
                parsed_script,
                self._label_index_for_parsed_script(parsed_script),
            )
        log_info(
            _LOGGER,
            "Recipe IO parsed script",
            project_name=parsed_script.project_name,
            alias_count=len(parsed_script.buffers),
            aliases=list(parsed_script.buffers.keys()),
            cube_ids=[
                str(buffer.get("cube_id", ""))
                for buffer in parsed_script.buffers.values()
            ],
            global_override_count=len(parsed_script.global_overrides),
            global_override_selection_count=len(
                parsed_script.global_override_selections
            ),
        )
        return parsed_script

    def _label_index_for_parsed_script(
        self,
        parsed_script: ParsedSugarScript,
    ) -> SugarScriptLabelIndex:
        """Build a label index for the aliases declared by one parsed script."""

        if self._cube_definition_provider is None:
            return SugarScriptLabelIndex.from_cube_graphs({})
        cube_graphs: dict[str, Mapping[str, JsonValue]] = {}
        for alias, buffer_data in parsed_script.buffers.items():
            cube_id = str(buffer_data.get("cube_id") or "")
            version = buffer_data.get("version")
            if isinstance(version, str) and version.strip():
                loaded = self._cube_definition_provider.load_cube_definition_version(
                    cube_id,
                    version.strip(),
                )
            else:
                loaded = self._cube_definition_provider.load_cube_definition(cube_id)
            cube_graphs[alias] = loaded.graph
        return SugarScriptLabelIndex.from_cube_graphs(cube_graphs)

    def _model_hashes_for_buffers(
        self,
        stripped_buffers: Mapping[str, Mapping[str, JsonValue]],
        ordered_aliases: list[str],
        *,
        model_hash_lookup: RecipeModelHashLookup | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return cache-known model hashes eligible for recipe serialization."""

        active_model_hash_lookup = model_hash_lookup or self._model_hash_lookup
        if active_model_hash_lookup is None:
            return {}
        model_hashes: dict[tuple[str, str, str], str] = {}
        for alias in ordered_aliases:
            buffer = stripped_buffers.get(alias, {})
            nodes = buffer.get("nodes")
            if not isinstance(nodes, Mapping):
                continue
            for node_name, node_data in nodes.items():
                if not isinstance(node_data, Mapping):
                    continue
                class_type = node_data.get("class_type")
                inputs = node_data.get("inputs")
                if not isinstance(inputs, Mapping):
                    continue
                for input_key, value in inputs.items():
                    if not isinstance(value, str):
                        continue
                    kind = model_kind_for_field(
                        class_type=str(class_type)
                        if isinstance(class_type, str)
                        else "",
                        input_key=str(input_key),
                    )
                    if kind is None:
                        continue
                    sha256 = active_model_hash_lookup.hash_for_model_value(
                        kind=kind,
                        value=value,
                    )
                    if sha256 is not None:
                        model_hashes[(alias, str(node_name), str(input_key))] = sha256
        return model_hashes

    def _prompt_lora_hashes_for_buffers(
        self,
        stripped_buffers: Mapping[str, Mapping[str, JsonValue]],
        ordered_aliases: list[str],
        *,
        serialization_context: RecipeSerializationContext | None = None,
    ) -> dict[tuple[str, str, str], OrderedDict[str, str]]:
        """Return cache-known hashes for inline LoRA tokens in prompt text fields."""

        prompt_lora_hash_lookup = (
            self._prompt_lora_hash_lookup
            if serialization_context is None
            else serialization_context.prompt_lora_hash_lookup
        )
        if prompt_lora_hash_lookup is None:
            return {}
        prompt_lora_hashes: dict[tuple[str, str, str], OrderedDict[str, str]] = {}
        for alias in ordered_aliases:
            buffer = stripped_buffers.get(alias, {})
            nodes = buffer.get("nodes")
            if not isinstance(nodes, Mapping):
                continue
            for node_name, node_data in nodes.items():
                if not isinstance(node_data, Mapping):
                    continue
                inputs = node_data.get("inputs")
                if not isinstance(inputs, Mapping):
                    continue
                for input_key, value in inputs.items():
                    if not isinstance(value, str) or "<lora:" not in value.casefold():
                        continue
                    field_hashes = self._prompt_lora_hashes_for_text(
                        value,
                        prompt_lora_hash_lookup=prompt_lora_hash_lookup,
                        serialization_context=serialization_context,
                    )
                    if field_hashes:
                        prompt_lora_hashes[(alias, str(node_name), str(input_key))] = (
                            field_hashes
                        )
        return prompt_lora_hashes

    def _prompt_lora_canonical_overrides_for_buffers(
        self,
        stripped_buffers: Mapping[str, Mapping[str, JsonValue]],
        ordered_aliases: list[str],
        *,
        serialization_context: RecipeSerializationContext | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return prompt-field overrides that replace found LoRAs with canonical names."""

        prompt_lora_hash_lookup = (
            self._prompt_lora_hash_lookup
            if serialization_context is None
            else serialization_context.prompt_lora_hash_lookup
        )
        if prompt_lora_hash_lookup is None:
            return {}
        prompt_overrides: dict[tuple[str, str, str], str] = {}
        for alias in ordered_aliases:
            buffer = stripped_buffers.get(alias, {})
            nodes = buffer.get("nodes")
            if not isinstance(nodes, Mapping):
                continue
            for node_name, node_data in nodes.items():
                if not isinstance(node_data, Mapping):
                    continue
                inputs = node_data.get("inputs")
                if not isinstance(inputs, Mapping):
                    continue
                for input_key, value in inputs.items():
                    if not isinstance(input_key, str) or not isinstance(value, str):
                        continue
                    if "<lora:" not in value.casefold():
                        continue
                    canonical_value = self._canonical_prompt_lora_text(
                        value,
                        prompt_lora_hash_lookup=prompt_lora_hash_lookup,
                    )
                    if canonical_value != value:
                        prompt_overrides[(alias, str(node_name), input_key)] = (
                            canonical_value
                        )
        return prompt_overrides

    def _canonical_prompt_lora_text(
        self,
        prompt_text: str,
        *,
        prompt_lora_hash_lookup: PromptLoraHashLookup,
    ) -> str:
        """Return prompt text with authoritatively known LoRA names canonicalized."""

        replacements: list[_PromptLoraNameReplacement] = []
        for lora_span in inline_lora_spans(prompt_text):
            backend_value = prompt_lora_hash_lookup.backend_value_for_prompt_lora_name(
                lora_span.prompt_name
            )
            if backend_value is None:
                continue
            canonical_name = prompt_lora_name_for_backend_value(backend_value)
            if canonical_name == lora_span.prompt_name:
                continue
            replacements.append(
                _PromptLoraNameReplacement(
                    start=lora_span.name_start,
                    end=lora_span.name_end,
                    value=canonical_name,
                )
            )
        return _replace_prompt_lora_names(prompt_text, replacements)

    def _prompt_lora_hashes_for_text(
        self,
        prompt_text: str,
        *,
        prompt_lora_hash_lookup: PromptLoraHashLookup,
        serialization_context: RecipeSerializationContext | None = None,
    ) -> OrderedDict[str, str]:
        """Return eligible inline LoRA hashes keyed by authored prompt name."""

        if serialization_context is not None:
            cached_hashes = serialization_context.prompt_lora_hashes_by_text.get(
                prompt_text
            )
            if cached_hashes is not None:
                return OrderedDict(cached_hashes.items())
        field_hashes: OrderedDict[str, str] = OrderedDict()
        seen_names: set[str] = set()
        for lora_span in inline_lora_spans(prompt_text):
            prompt_name = lora_span.prompt_name
            normalized_name = normalized_prompt_lora_name(prompt_name)
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            sha256 = _prompt_lora_sha_for_name(
                prompt_name=prompt_name,
                prompt_lora_hash_lookup=prompt_lora_hash_lookup,
                serialization_context=serialization_context,
            )
            if sha256 is None:
                continue
            field_hashes[prompt_name] = sha256.upper()
        if serialization_context is not None:
            serialization_context.prompt_lora_hashes_by_text[prompt_text] = OrderedDict(
                field_hashes.items()
            )
        return field_hashes

    def load_and_parse_recipe_document(self, path: Path) -> ParsedRecipeDocument:
        """Load recipe text from disk and parse it for workflow ingestion."""

        loaded_document = self.load_recipe_document(path)
        parsed_script = self.parse_recipe_script(loaded_document.sugar_script_text)
        log_debug(
            _LOGGER,
            "Recipe IO load and parse completed",
            path=loaded_document.source_path,
            source_kind=loaded_document.source_kind,
            project_name=parsed_script.project_name,
            alias_count=len(parsed_script.buffers),
            global_override_count=len(parsed_script.global_overrides),
            global_override_selection_count=len(
                parsed_script.global_override_selections
            ),
        )
        return ParsedRecipeDocument(
            loaded_document=loaded_document,
            parsed_script=parsed_script,
        )


__all__ = [
    "ParsedRecipeDocument",
    "RecipeDocumentClassification",
    "RecipeIoService",
]


def _log_image_inputs_seen_for_serialization(
    *,
    stripped_buffers: Mapping[str, Mapping[str, JsonValue]],
    ordered_aliases: list[str],
) -> None:
    """Log LoadImage values present in workflow buffers before Sugar encoding."""

    for cube_alias in ordered_aliases:
        buffer = stripped_buffers.get(cube_alias, {})
        nodes = buffer.get("nodes", {})
        if not isinstance(nodes, Mapping):
            continue
        for node_name, node_data in nodes.items():
            if not isinstance(node_data, Mapping):
                continue
            node_class = node_data.get("class_type")
            if node_class not in _LOAD_IMAGE_CLASSES:
                continue
            inputs = node_data.get("inputs", {})
            image_value = inputs.get("image") if isinstance(inputs, Mapping) else None
            log_debug(
                _LOGGER,
                "Serializing workflow image input",
                ordered_aliases=ordered_aliases,
                cube_alias=cube_alias,
                node_name=node_name,
                node_class=node_class,
                image_value=image_value,
            )


def _session_model_hash_lookup(
    model_hash_lookup: RecipeModelHashLookup | None,
) -> RecipeModelHashLookup | None:
    """Return a request-scoped model hash lookup when the collaborator supports it."""

    if model_hash_lookup is None:
        return None
    create_session = getattr(model_hash_lookup, "create_session", None)
    if callable(create_session):
        return cast(RecipeModelHashLookup, create_session())
    return model_hash_lookup


def _session_prompt_lora_hash_lookup(
    prompt_lora_hash_lookup: PromptLoraHashLookup | None,
) -> PromptLoraHashLookup | None:
    """Return a request-scoped prompt LoRA hash lookup when available."""

    if prompt_lora_hash_lookup is None:
        return None
    create_session = getattr(prompt_lora_hash_lookup, "create_session", None)
    if callable(create_session):
        return cast(PromptLoraHashLookup, create_session())
    return prompt_lora_hash_lookup


def _replace_prompt_lora_names(
    prompt_text: str,
    replacements: list[_PromptLoraNameReplacement],
) -> str:
    """Rewrite parsed inline LoRA token names while preserving token syntax."""

    rewritten = prompt_text
    for replacement in sorted(replacements, key=lambda item: item.start, reverse=True):
        rewritten = (
            rewritten[: replacement.start]
            + replacement.value
            + rewritten[replacement.end :]
        )
    return rewritten


def _prompt_lora_sha_for_name(
    *,
    prompt_name: str,
    prompt_lora_hash_lookup: PromptLoraHashLookup,
    serialization_context: RecipeSerializationContext | None,
) -> str | None:
    """Return one prompt LoRA SHA while caching normalized names in the context."""

    if serialization_context is None:
        return prompt_lora_hash_lookup.hash_for_prompt_lora_name(prompt_name)
    normalized_name = normalized_prompt_lora_name(prompt_name)
    if normalized_name not in serialization_context.prompt_lora_sha_by_normalized_name:
        sha256 = prompt_lora_hash_lookup.hash_for_prompt_lora_name(prompt_name)
        serialization_context.prompt_lora_sha_by_normalized_name[normalized_name] = (
            sha256.upper() if sha256 is not None else None
        )
    return serialization_context.prompt_lora_sha_by_normalized_name[normalized_name]


def _text_sha256(value: str) -> str:
    """Return a short deterministic hash for recipe text without logging content."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _validate_recipe_destination_path(destination_path: Path) -> Path:
    """Return a resolved recipe path that is safe to write explicitly."""

    resolved_path = destination_path.resolve()
    if resolved_path.exists() and resolved_path.is_dir():
        raise ValueError(f"Workflow recipe destination is a directory: {resolved_path}")
    if not _is_supported_recipe_extension(resolved_path):
        raise ValueError(
            f"Workflow recipe destination must use .sugar: {resolved_path}"
        )
    parent = resolved_path.parent
    if parent.exists() and not parent.is_dir():
        raise ValueError(f"Workflow recipe parent path is not a directory: {parent}")
    return resolved_path


def _is_supported_recipe_extension(path: Path) -> bool:
    """Return whether one path uses a supported Sugar recipe extension."""

    return path.suffix.lower() == ".sugar"
