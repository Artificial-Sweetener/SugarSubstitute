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

"""Resolve wildcard prompts on generation-only workflow copies."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from typing import Any, Protocol, TypeVar, cast

from substitute.domain.links import PromptEndpointIndex
from substitute.domain.prompt import (
    PromptWildcardSyntaxProfile,
    parse_prompt_document,
)
from substitute.shared.logging.logger import get_logger, log_debug

from .resolver import (
    PromptWildcardResolutionContext,
    PromptWildcardResolver,
    PromptWildcardSourceProvider,
)
from .preprocessing_context import (
    PromptWildcardPreprocessingContext,
    WildcardExactResolutionCacheKey,
    WildcardPromptFieldSeedKey,
    WildcardShouldResolveCacheKey,
)
from .preferences import PromptWildcardPreferenceService
from .seed_policy import (
    PromptWildcardSeedPolicy,
    PromptWildcardSeedSelection,
    PromptWildcardSeedWorkflow,
)

_LOGGER = get_logger("application.prompt_wildcards.preprocessing_service")
_WILDCARD_PROMPT_CLASS_TYPES = frozenset(
    {
        "CLIPTextEncode",
        "CLIPTextEncodeSDXL",
        "CSVWildcardNode",
        "String",
    }
)
_PROMPT_INPUT_KEYS = frozenset({"prompt_template", "text", "value"})
_PromptEndpointFieldsByCube = dict[str, frozenset[tuple[str, str]]]
_PromptFieldOverrides = Mapping[tuple[str, str, str], str]


class PromptWildcardWorkflow(PromptWildcardSeedWorkflow, Protocol):
    """Describe mutable workflow state used by wildcard preprocessing."""

    global_overrides: Any


_WorkflowT = TypeVar("_WorkflowT")


class PromptWildcardPreprocessingService:
    """Resolve wildcard prompt text on copied workflow state before generation."""

    def __init__(
        self,
        *,
        source_provider: PromptWildcardSourceProvider,
        seed_policy: PromptWildcardSeedPolicy | None = None,
        syntax_profile: PromptWildcardSyntaxProfile | None = None,
        preference_service: PromptWildcardPreferenceService | None = None,
        resolve_on_generation: bool = True,
    ) -> None:
        """Store preprocessing collaborators and settings."""

        self._source_provider = source_provider
        self._seed_policy = seed_policy or PromptWildcardSeedPolicy()
        self._syntax_profile = syntax_profile or PromptWildcardSyntaxProfile.default()
        self._preference_service = preference_service
        self._resolve_on_generation = resolve_on_generation

    def preprocess_workflow(
        self,
        *,
        workflow: _WorkflowT,
        workflow_id: str,
        wildcard_context: PromptWildcardResolutionContext | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> _WorkflowT:
        """Return a generation-only workflow copy with prompt wildcards resolved."""

        return self.preprocess_workflow_copy(
            workflow=workflow,
            workflow_id=workflow_id,
            wildcard_context=wildcard_context,
            preprocessing_context=preprocessing_context,
            prompt_endpoint_index=prompt_endpoint_index,
        )

    def preprocess_workflow_copy(
        self,
        *,
        workflow: _WorkflowT,
        workflow_id: str,
        wildcard_context: PromptWildcardResolutionContext | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> _WorkflowT:
        """Return a generation-only workflow copy with prompt wildcards resolved."""

        workflow_copy = deepcopy(workflow)
        self.preprocess_workflow_in_place(
            workflow=workflow_copy,
            workflow_id=workflow_id,
            wildcard_context=wildcard_context,
            preprocessing_context=preprocessing_context,
            prompt_endpoint_index=prompt_endpoint_index,
        )
        return workflow_copy

    def preprocess_workflow_in_place(
        self,
        *,
        workflow: _WorkflowT,
        workflow_id: str,
        wildcard_context: PromptWildcardResolutionContext | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> None:
        """Resolve wildcard prompt text on a mutable generation workflow copy."""

        typed_workflow = cast(PromptWildcardWorkflow, workflow)
        request_context = self._preprocessing_context(
            wildcard_context=wildcard_context,
            preprocessing_context=preprocessing_context,
        )
        resolve_on_generation, syntax_profile = self._preprocessing_settings(
            request_context
        )
        if not resolve_on_generation:
            return

        resolver = PromptWildcardResolver(
            self._source_provider,
            syntax_profile=syntax_profile,
        )
        prompt_endpoint_fields = _prompt_endpoint_fields_by_cube(prompt_endpoint_index)
        for cube_alias in typed_workflow.stack_order:
            cube = typed_workflow.cubes.get(cube_alias)
            if cube is None:
                continue
            self._resolve_cube_prompts(
                workflow=typed_workflow,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube=cube,
                resolver=resolver,
                syntax_profile=syntax_profile,
                preprocessing_context=request_context,
                prompt_endpoint_fields=prompt_endpoint_fields,
            )

    def resolve_workflow_prompt_field_overrides(
        self,
        *,
        workflow: _WorkflowT,
        workflow_id: str,
        prompt_field_overrides: _PromptFieldOverrides | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return prompt-field values with wildcard preprocessing applied."""

        typed_workflow = cast(PromptWildcardWorkflow, workflow)
        request_context = self._preprocessing_context(
            wildcard_context=None,
            preprocessing_context=preprocessing_context,
        )
        effective_overrides = dict(prompt_field_overrides or {})
        resolve_on_generation, syntax_profile = self._preprocessing_settings(
            request_context
        )
        if not resolve_on_generation:
            return effective_overrides

        resolver = PromptWildcardResolver(
            self._source_provider,
            syntax_profile=syntax_profile,
        )
        prompt_endpoint_fields = _prompt_endpoint_fields_by_cube(prompt_endpoint_index)
        for cube_alias in typed_workflow.stack_order:
            cube = typed_workflow.cubes.get(cube_alias)
            if cube is None:
                continue
            self._resolve_cube_prompt_overrides(
                workflow=typed_workflow,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                cube=cube,
                resolver=resolver,
                syntax_profile=syntax_profile,
                preprocessing_context=request_context,
                prompt_endpoint_fields=prompt_endpoint_fields,
                effective_overrides=effective_overrides,
            )
        return effective_overrides

    def _resolve_cube_prompts(
        self,
        *,
        workflow: PromptWildcardWorkflow,
        workflow_id: str,
        cube_alias: str,
        cube: Any,
        resolver: PromptWildcardResolver,
        syntax_profile: PromptWildcardSyntaxProfile,
        preprocessing_context: PromptWildcardPreprocessingContext,
        prompt_endpoint_fields: _PromptEndpointFieldsByCube,
    ) -> None:
        """Resolve wildcard-bearing prompt inputs in one cube."""

        buffer = getattr(cube, "buffer", None)
        if not isinstance(buffer, MutableMapping):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, MutableMapping):
            return
        for node_name, node in nodes.items():
            if not isinstance(node_name, str) or not isinstance(node, MutableMapping):
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str) or not isinstance(
                inputs, MutableMapping
            ):
                continue
            for input_key, value in tuple(inputs.items()):
                if not isinstance(input_key, str) or not isinstance(value, str):
                    continue
                if not self._should_resolve_input(
                    class_type,
                    input_key,
                    value,
                    is_prompt_endpoint=_is_prompt_endpoint_field(
                        prompt_endpoint_fields,
                        cube_alias=cube_alias,
                        node_name=node_name,
                        input_key=input_key,
                    ),
                    syntax_profile=syntax_profile,
                    preprocessing_context=preprocessing_context,
                ):
                    continue
                seed_selection = self._select_seed(
                    workflow=workflow,
                    prompt_cube_alias=cube_alias,
                    workflow_id=workflow_id,
                    prompt_node_name=node_name,
                    prompt_field_key=input_key,
                    preprocessing_context=preprocessing_context,
                )
                effective_seed = (
                    preprocessing_context.resolution_context.effective_seed(
                        seed_selection.seed
                    )
                )
                resolution_key = WildcardExactResolutionCacheKey(
                    prompt_text=value,
                    effective_seed=effective_seed,
                    syntax_profile=syntax_profile,
                )
                if resolution_key in preprocessing_context.exact_resolution_by_text:
                    preprocessing_context.exact_resolution_cache_hits += 1
                    resolution = preprocessing_context.exact_resolution_by_text[
                        resolution_key
                    ]
                else:
                    preprocessing_context.exact_resolution_cache_misses += 1
                    resolution = resolver.resolve(
                        value,
                        seed=seed_selection.seed,
                        context=preprocessing_context.resolution_context,
                    )
                    preprocessing_context.exact_resolution_by_text[resolution_key] = (
                        resolution
                    )
                if resolution.resolved_text == value:
                    continue
                inputs[input_key] = resolution.resolved_text
                log_debug(
                    _LOGGER,
                    "Resolved wildcard prompt input for generation.",
                    workflow_id=workflow_id,
                    cube_alias=cube_alias,
                    prompt_node_name=node_name,
                    prompt_field_key=input_key,
                    replacement_count=len(resolution.replacements),
                )

    def _resolve_cube_prompt_overrides(
        self,
        *,
        workflow: PromptWildcardWorkflow,
        workflow_id: str,
        cube_alias: str,
        cube: Any,
        resolver: PromptWildcardResolver,
        syntax_profile: PromptWildcardSyntaxProfile,
        preprocessing_context: PromptWildcardPreprocessingContext,
        prompt_endpoint_fields: _PromptEndpointFieldsByCube,
        effective_overrides: dict[tuple[str, str, str], str],
    ) -> None:
        """Resolve wildcard-bearing effective prompt values for one cube."""

        buffer = getattr(cube, "buffer", None)
        if not isinstance(buffer, Mapping):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return
        for node_name, node in nodes.items():
            if not isinstance(node_name, str) or not isinstance(node, Mapping):
                continue
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(class_type, str) or not isinstance(inputs, Mapping):
                continue
            for input_key, value in inputs.items():
                if not isinstance(input_key, str) or not isinstance(value, str):
                    continue
                field_key = (cube_alias, node_name, input_key)
                effective_value = effective_overrides.get(field_key, value)
                if not self._should_resolve_input(
                    class_type,
                    input_key,
                    effective_value,
                    is_prompt_endpoint=_is_prompt_endpoint_field(
                        prompt_endpoint_fields,
                        cube_alias=cube_alias,
                        node_name=node_name,
                        input_key=input_key,
                    ),
                    syntax_profile=syntax_profile,
                    preprocessing_context=preprocessing_context,
                ):
                    continue
                seed_selection = self._select_seed(
                    workflow=workflow,
                    prompt_cube_alias=cube_alias,
                    workflow_id=workflow_id,
                    prompt_node_name=node_name,
                    prompt_field_key=input_key,
                    preprocessing_context=preprocessing_context,
                )
                effective_seed = (
                    preprocessing_context.resolution_context.effective_seed(
                        seed_selection.seed
                    )
                )
                resolution_key = WildcardExactResolutionCacheKey(
                    prompt_text=effective_value,
                    effective_seed=effective_seed,
                    syntax_profile=syntax_profile,
                )
                if resolution_key in preprocessing_context.exact_resolution_by_text:
                    preprocessing_context.exact_resolution_cache_hits += 1
                    resolution = preprocessing_context.exact_resolution_by_text[
                        resolution_key
                    ]
                else:
                    preprocessing_context.exact_resolution_cache_misses += 1
                    resolution = resolver.resolve(
                        effective_value,
                        seed=seed_selection.seed,
                        context=preprocessing_context.resolution_context,
                    )
                    preprocessing_context.exact_resolution_by_text[resolution_key] = (
                        resolution
                    )
                if resolution.resolved_text != effective_value:
                    effective_overrides[field_key] = resolution.resolved_text
                    log_debug(
                        _LOGGER,
                        "Resolved wildcard prompt input overlay for generation.",
                        workflow_id=workflow_id,
                        cube_alias=cube_alias,
                        prompt_node_name=node_name,
                        prompt_field_key=input_key,
                        replacement_count=len(resolution.replacements),
                    )

    def _should_resolve_input(
        self,
        class_type: str,
        input_key: str,
        value: str,
        *,
        is_prompt_endpoint: bool = False,
        syntax_profile: PromptWildcardSyntaxProfile,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
    ) -> bool:
        """Return whether one string input should be wildcard-resolved."""

        if input_key not in _PROMPT_INPUT_KEYS:
            return False
        if not is_prompt_endpoint and class_type not in _WILDCARD_PROMPT_CLASS_TYPES:
            return False
        cache_key = WildcardShouldResolveCacheKey(
            prompt_text=value,
            syntax_profile=syntax_profile,
        )
        if (
            preprocessing_context is not None
            and cache_key in preprocessing_context.should_resolve_by_text
        ):
            return preprocessing_context.should_resolve_by_text[cache_key]
        document = parse_prompt_document(
            value,
            wildcard_syntax_profile=syntax_profile,
        )
        should_resolve = bool(document.wildcard_spans)
        if preprocessing_context is not None:
            preprocessing_context.should_resolve_by_text[cache_key] = should_resolve
        return should_resolve

    def _select_seed(
        self,
        *,
        workflow: PromptWildcardWorkflow,
        prompt_cube_alias: str,
        workflow_id: str,
        prompt_node_name: str,
        prompt_field_key: str,
        preprocessing_context: PromptWildcardPreprocessingContext,
    ) -> PromptWildcardSeedSelection:
        """Return request-cached seed selection for one prompt field."""

        cache_key = WildcardPromptFieldSeedKey(
            workflow_id=workflow_id,
            prompt_cube_alias=prompt_cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        if cache_key not in preprocessing_context.seed_selection_by_field:
            preprocessing_context.seed_selection_by_field[cache_key] = (
                self._seed_policy.select_seed(
                    workflow=workflow,
                    prompt_cube_alias=prompt_cube_alias,
                    workflow_id=workflow_id,
                    prompt_node_name=prompt_node_name,
                    prompt_field_key=prompt_field_key,
                )
            )
        return preprocessing_context.seed_selection_by_field[cache_key]

    def _preprocessing_context(
        self,
        *,
        wildcard_context: PromptWildcardResolutionContext | None,
        preprocessing_context: PromptWildcardPreprocessingContext | None,
    ) -> PromptWildcardPreprocessingContext:
        """Return the request context used by this preprocessing pass."""

        if preprocessing_context is not None:
            return preprocessing_context
        return PromptWildcardPreprocessingContext(
            resolution_context=wildcard_context or PromptWildcardResolutionContext()
        )

    def _preprocessing_settings(
        self,
        context: PromptWildcardPreprocessingContext,
    ) -> tuple[bool, PromptWildcardSyntaxProfile]:
        """Return request-cached wildcard preference settings."""

        if context.resolve_on_generation is None or context.syntax_profile is None:
            resolve_on_generation = self._resolve_on_generation
            syntax_profile = self._syntax_profile
            if self._preference_service is not None:
                preferences = self._preference_service.load_preferences()
                resolve_on_generation = preferences.resolve_on_generation
                syntax_profile = preferences.syntax_profile()
            context.resolve_on_generation = resolve_on_generation
            context.syntax_profile = syntax_profile
        return context.resolve_on_generation, context.syntax_profile


__all__ = [
    "PromptWildcardPreprocessingContext",
    "PromptWildcardPreprocessingService",
    "PromptWildcardWorkflow",
]


def _prompt_endpoint_fields_by_cube(
    prompt_endpoint_index: PromptEndpointIndex | None,
) -> _PromptEndpointFieldsByCube:
    """Return semantic prompt fields keyed by cube for generation preprocessing."""

    if prompt_endpoint_index is None:
        return {}
    fields_by_cube: dict[str, set[tuple[str, str]]] = {}
    for endpoint in prompt_endpoint_index.endpoints:
        fields_by_cube.setdefault(endpoint.cube_alias, set()).add(
            (endpoint.node_name, endpoint.field_key)
        )
    return {
        cube_alias: frozenset(fields) for cube_alias, fields in fields_by_cube.items()
    }


def _is_prompt_endpoint_field(
    prompt_endpoint_fields: _PromptEndpointFieldsByCube,
    *,
    cube_alias: str,
    node_name: str,
    input_key: str,
) -> bool:
    """Return whether one node input is owned by semantic prompt behavior."""

    return (node_name, input_key) in prompt_endpoint_fields.get(cube_alias, frozenset())
