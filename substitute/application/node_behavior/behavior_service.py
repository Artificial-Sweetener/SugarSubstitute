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

"""Resolve editor node behavior into one application-owned snapshot per refresh."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Mapping, Protocol

from substitute.application.cubes.cube_load_service import LoadedCubeDefinition
from substitute.application.model_metadata import model_kind_for_field
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.workflows.prompt_endpoint_service import (
    PromptEndpointService,
)
from substitute.application.workflows.node_link_endpoint_service import (
    NodeLinkEndpointService,
)
from substitute.domain.comfy_workflow import NodeActivationStorage
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.links.node_links import NodeLinkEndpointIndex
from substitute.domain.node_behavior import (
    NodeBehaviorContext,
    NodeBehaviorPatch,
    PackageBehaviorPatch,
    ResolvedNodeBehavior,
    EditorBehaviorContext,
    FieldPresentation,
    compute_editor_behavior,
    merge_node_behavior_patches,
    resolve_node_behavior,
)
from substitute.domain.node_behavior.prompt_graph import (
    PromptDetectionResult,
    PromptGraphContext,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
)

from .field_classification import NodeFieldKind, classify_node_field
from .direct_output_behavior_inference_service import (
    DirectOutputBehaviorInferenceService,
)
from .list_value_resolver import (
    extract_live_list_options,
    is_choice_field_type,
    resolve_live_list_value,
    unresolved_choice_options_reason,
)
from .model_backed_node_detector import ModelBackedNodeDetector
from .models import EditorBehaviorSnapshot, FieldValueSource, ResolvedFieldSpec
from .prompt_behavior_inference_service import PromptBehaviorInferenceService
from .section_node_source import (
    SectionNodeSourceFactory,
    is_subgraph_wrapper_definition,
)
from .section_card_order_service import SectionCardOrderService

_LOGGER = get_logger("application.node_behavior.behavior_service")


class CubeStateProtocol(Protocol):
    """Describe the cube-state shape consumed by NodeBehaviorService."""

    buffer: dict[str, object]
    ui: dict[str, object]
    dirty: bool

    @property
    def activation_storage(self) -> NodeActivationStorage | str:
        """Return the graph's authoritative node activation storage mode."""

    @property
    def uses_node_titles_as_card_labels(self) -> bool:
        """Return whether source node titles own visible card labels."""


@dataclass
class NodeBehaviorRuntimeState:
    """Store per-cube runtime node-behavior state that should not enter recipe buffers."""

    node_instance_patch: PackageBehaviorPatch = field(
        default_factory=PackageBehaviorPatch
    )


class NodeBehaviorService:
    """Resolve inferred and runtime node behavior for the editor."""

    def __init__(
        self,
        *,
        node_definition_gateway: NodeDefinitionGateway,
        model_backed_node_detector: ModelBackedNodeDetector | None = None,
    ) -> None:
        """Initialize the service with live node-definition collaborators."""

        self._section_node_source_factory = SectionNodeSourceFactory(
            node_definition_gateway
        )
        self._model_backed_node_detector = model_backed_node_detector
        self._prompt_endpoint_service = PromptEndpointService()
        self._node_link_endpoint_service = NodeLinkEndpointService()
        self._prompt_behavior_inference_service = PromptBehaviorInferenceService()
        self._direct_output_behavior_inference_service = (
            DirectOutputBehaviorInferenceService()
        )
        self._section_card_order_service = SectionCardOrderService()

    @staticmethod
    def ensure_runtime_state(cube_state: CubeStateProtocol) -> NodeBehaviorRuntimeState:
        """Return the runtime behavior state object stored on one cube state."""

        ui_payload = getattr(cube_state, "ui", None)
        if not isinstance(ui_payload, dict):
            ui_payload = {}
            cube_state.ui = ui_payload
        runtime_state = ui_payload.get("node_behavior_runtime")
        if isinstance(runtime_state, NodeBehaviorRuntimeState):
            return runtime_state
        runtime_state = NodeBehaviorRuntimeState()
        ui_payload["node_behavior_runtime"] = runtime_state
        return runtime_state

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Build runtime node-behavior state for one loaded cube."""

        _ = loaded_cube, alias_name
        runtime_state = NodeBehaviorRuntimeState()
        return runtime_state

    def build_snapshot(
        self,
        *,
        cube_states: Mapping[str, CubeStateProtocol],
        stack_order: list[str],
        workflow_overrides: Mapping[str, object] | None = None,
        search_hidden_keys: set[object] | None = None,
        override_hidden_field_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
    ) -> EditorBehaviorSnapshot:
        """Resolve node behavior and compute editor runtime decisions for one refresh pass."""

        snapshot_started_at = perf_counter()
        resolved_by_alias: dict[str, dict[str, ResolvedNodeBehavior]] = {}
        field_specs_by_alias: dict[str, dict[str, dict[str, ResolvedFieldSpec]]] = {}
        declarative_by_alias: dict[str, PackageBehaviorPatch | None] = {}
        prompt_detection_results_by_alias: dict[str, PromptDetectionResult] = {}
        prompt_contexts_by_alias: dict[str, tuple[PromptGraphContext, ...]] = {}
        baseline_order_by_alias: dict[str, tuple[str, ...]] = {}
        node_count = 0
        field_count = 0
        node_definition_lookup_count = 0
        unique_class_types: set[str] = set()
        for alias in stack_order:
            cube_state = cube_states.get(alias)
            if cube_state is None:
                continue
            is_loaded_cube = self._is_loaded_cube_state(cube_state)
            declarative_patch = None
            runtime_state = self.ensure_runtime_state(cube_state)
            declarative_by_alias[alias] = declarative_patch
            buffer = getattr(cube_state, "buffer", {}) if cube_state is not None else {}
            per_node: dict[str, ResolvedNodeBehavior] = {}
            per_node_specs: dict[str, dict[str, ResolvedFieldSpec]] = {}
            sources = self._section_node_source_factory.prepare(
                alias=alias,
                buffer=buffer,
            )
            baseline_order_by_alias[alias] = tuple(
                source.node_name for source in sources
            )
            node_count += len(sources)
            node_definition_lookup_count += len(sources)
            unique_class_types.update(source.class_type for source in sources)
            prompt_inference = self._prompt_behavior_inference_service.infer(sources)
            graph_nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
            output_patches = (
                self._direct_output_behavior_inference_service.infer(
                    graph=graph_nodes if isinstance(graph_nodes, Mapping) else {},
                    sources=sources,
                )
                if isinstance(cube_state, DirectWorkflowState)
                else {}
            )
            prompt_detection_results_by_alias[alias] = prompt_inference.detection_result
            prompt_contexts_by_alias[alias] = prompt_inference.graph_contexts
            if prompt_inference.detection_result.ambiguities:
                log_debug(
                    _LOGGER,
                    "Withheld ambiguous prompt behavior",
                    cube_alias=alias,
                    ambiguity_count=len(prompt_inference.detection_result.ambiguities),
                )
            for source in sources:
                node_name = source.node_name
                node_data = source.node_data
                class_type = source.class_type
                live_definition = source.node_definition
                input_keys = source.input_keys
                instance_key = f"{alias}:{node_name}"
                context = self._build_node_context(
                    alias=alias,
                    stack_order=stack_order,
                    node_name=node_name,
                    class_type=class_type,
                    node_title=source.node_title,
                    live_definition=live_definition,
                    declarative_patch=declarative_patch,
                    hook_patch=None,
                    workflow_overrides=workflow_overrides or {},
                    runtime_patch=(
                        runtime_state.node_instance_patch.by_node_instance.get(
                            instance_key
                        )
                        if runtime_state.node_instance_patch.by_node_instance
                        else None
                    ),
                    graph_inference_patch=merge_node_behavior_patches(
                        prompt_inference.patches_by_node.get(
                            node_name,
                            NodeBehaviorPatch(),
                        ),
                        output_patches.get(node_name, NodeBehaviorPatch()),
                    ),
                )
                resolved = resolve_node_behavior(
                    node_name=node_name,
                    class_type=class_type,
                    input_keys=input_keys,
                    context=context,
                )
                if (
                    bool(
                        getattr(
                            cube_state,
                            "uses_node_titles_as_card_labels",
                            False,
                        )
                    )
                    and context.node_title is not None
                ):
                    resolved = replace(resolved, display_name=context.node_title)
                elif is_subgraph_wrapper_definition(live_definition):
                    resolved = replace(resolved, display_name=context.node_title)
                resolved = self._with_node_tooltip(
                    live_definition=live_definition,
                    resolved_behavior=resolved,
                )
                resolved = self._with_model_default_icon(
                    node_data=node_data,
                    live_definition=live_definition,
                    resolved_behavior=resolved,
                )
                per_node[node_name] = resolved
                node_field_specs = self._build_field_specs(
                    cube_state=cube_state,
                    alias=alias,
                    node_name=node_name,
                    class_type=class_type,
                    input_keys=input_keys,
                    node_data=node_data,
                    live_definition=live_definition,
                    resolved_behavior=resolved,
                    is_loaded_cube=is_loaded_cube,
                )
                field_count += len(node_field_specs)
                per_node_specs[node_name] = node_field_specs
            resolved_by_alias[alias] = per_node
            field_specs_by_alias[alias] = per_node_specs

        prompt_endpoint_index = self._prompt_endpoint_service.build_index(
            resolved_by_alias
        )
        node_link_endpoint_index = self._node_link_endpoint_service.build_index(
            cube_states=cube_states,
            stack_order=stack_order,
            resolved_nodes_by_alias=resolved_by_alias,
            prompt_endpoint_index=prompt_endpoint_index,
        )

        ctx = EditorBehaviorContext(
            stack_order=tuple(stack_order),
            cubes=cube_states,
            behaviors_by_alias=resolved_by_alias,
            workflow_overrides=workflow_overrides or {},
            search_hidden_keys=frozenset(search_hidden_keys or set()),
            override_hidden_field_keys=frozenset(override_hidden_field_keys or set()),
            prompt_endpoint_index=prompt_endpoint_index,
            node_link_endpoint_index=node_link_endpoint_index,
            node_search_text=node_search_text,
            search_matching_nodes=(
                frozenset(search_matching_nodes)
                if search_matching_nodes is not None
                else None
            ),
        )
        card_decisions, hidden_keys, reveal_entries = compute_editor_behavior(
            ctx,
            declarative_by_alias=declarative_by_alias,
        )
        card_order_by_alias = self._section_card_order_service.plan(
            section_states=cube_states,
            section_order=stack_order,
            baseline_order_by_alias=baseline_order_by_alias,
            field_specs_by_alias=field_specs_by_alias,
            card_decisions_by_alias=card_decisions,
            prompt_contexts_by_alias=prompt_contexts_by_alias,
        )
        snapshot = EditorBehaviorSnapshot(
            resolved_nodes_by_alias=resolved_by_alias,
            field_specs_by_alias=field_specs_by_alias,
            prompt_endpoint_index=prompt_endpoint_index,
            node_link_endpoint_index=node_link_endpoint_index,
            card_decisions_by_alias=card_decisions,
            hidden_field_keys_by_alias=hidden_keys,
            reveal_entries_by_alias=reveal_entries,
            prompt_detection_results_by_alias=prompt_detection_results_by_alias,
            prompt_contexts_by_alias=prompt_contexts_by_alias,
            card_order_by_alias=card_order_by_alias,
        )
        log_timing(
            _LOGGER,
            "Built editor behavior snapshot",
            started_at=snapshot_started_at,
            cube_section_count=len(stack_order),
            node_count=node_count,
            field_count=field_count,
            unique_class_count=len(unique_class_types),
            node_definition_lookup_count=node_definition_lookup_count,
        )
        return snapshot

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, CubeStateProtocol],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return prompt endpoints using the same behavior path as editor snapshots."""

        return self.build_snapshot(
            cube_states=cube_states,
            stack_order=stack_order,
        ).prompt_endpoint_index

    def build_link_endpoint_indexes(
        self,
        cube_states: Mapping[str, CubeStateProtocol],
        stack_order: list[str],
    ) -> tuple[PromptEndpointIndex, NodeLinkEndpointIndex]:
        """Return prompt and node-link endpoint indexes from one behavior snapshot."""

        snapshot = self.build_snapshot(
            cube_states=cube_states,
            stack_order=stack_order,
        )
        return snapshot.prompt_endpoint_index, snapshot.node_link_endpoint_index

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, CubeStateProtocol],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return node-link endpoints using the editor snapshot resolution path."""

        return self.build_snapshot(
            cube_states=cube_states,
            stack_order=stack_order,
        ).node_link_endpoint_index

    def set_node_activation_override(
        self,
        cube_state: CubeStateProtocol,
        node_name: str,
        explicit_enabled: bool | None,
    ) -> None:
        """Persist one explicit node activation override into the workflow buffer."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            return
        node_payload = nodes.get(node_name)
        if not isinstance(node_payload, dict):
            return

        activation_storage = getattr(
            cube_state,
            "activation_storage",
            NodeActivationStorage.ENABLED_OVERRIDE,
        )
        if str(activation_storage) in {
            NodeActivationStorage.COMFY_MODE,
            NodeActivationStorage.COMFY_MODE.value,
        }:
            set_node_activation = getattr(cube_state, "set_node_activation", None)
            if callable(set_node_activation):
                set_node_activation(node_name, explicit_enabled is not False)
            return

        previous = node_payload.get("enabled") if "enabled" in node_payload else None
        if explicit_enabled is None:
            if "enabled" in node_payload:
                node_payload.pop("enabled", None)
                cube_state.dirty = True
            return
        if previous == bool(explicit_enabled):
            return
        node_payload["enabled"] = bool(explicit_enabled)
        cube_state.dirty = True

    def set_node_visibility_override(
        self,
        cube_state: CubeStateProtocol,
        node_name: str,
        explicit_revealed: bool | None,
    ) -> None:
        """Persist one explicit editor reveal override into the workflow buffer."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            return
        node_payload = nodes.get(node_name)
        if not isinstance(node_payload, dict):
            return

        previous = node_payload.get("revealed") if "revealed" in node_payload else None
        if explicit_revealed is None:
            if "revealed" in node_payload:
                node_payload.pop("revealed", None)
                cube_state.dirty = True
            return
        if explicit_revealed is not True:
            return
        if previous is True:
            return
        node_payload["revealed"] = True
        cube_state.dirty = True

    def toggle_node_activation_override(
        self,
        cube_state: CubeStateProtocol,
        node_name: str,
    ) -> None:
        """Toggle one explicit node activation override between reveal and inherit."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return
        nodes = buffer.get("nodes")
        if not isinstance(nodes, dict):
            return
        node_payload = nodes.get(node_name)
        if not isinstance(node_payload, dict):
            return

        activation_storage = getattr(
            cube_state,
            "activation_storage",
            NodeActivationStorage.ENABLED_OVERRIDE,
        )
        if str(activation_storage) in {
            NodeActivationStorage.COMFY_MODE,
            NodeActivationStorage.COMFY_MODE.value,
        }:
            self.set_node_activation_override(
                cube_state,
                node_name,
                node_payload.get("mode", 0) == 4,
            )
            return

        current = node_payload.get("enabled") if "enabled" in node_payload else None
        next_override = None if current is True else True
        self.set_node_activation_override(cube_state, node_name, next_override)

    def _build_node_context(
        self,
        *,
        alias: str,
        stack_order: list[str],
        node_name: str,
        class_type: str,
        node_title: str | None,
        live_definition: Mapping[str, object] | None,
        declarative_patch: PackageBehaviorPatch | None,
        hook_patch: PackageBehaviorPatch | None,
        workflow_overrides: Mapping[str, object],
        runtime_patch: NodeBehaviorPatch | None,
        graph_inference_patch: NodeBehaviorPatch | None,
    ) -> NodeBehaviorContext:
        """Return the domain resolution context for one node instance."""

        return NodeBehaviorContext(
            stack_order=tuple(stack_order),
            cube_alias=alias,
            node_name=node_name,
            class_type=class_type,
            node_title=node_title,
            live_node_definition=live_definition,
            declarative_patch=declarative_patch,
            hook_patch=hook_patch,
            workflow_overrides=workflow_overrides,
            node_instance_patch=runtime_patch if runtime_patch is not None else None,
            graph_inference_patch=graph_inference_patch,
        )

    def _with_model_default_icon(
        self,
        *,
        node_data: Mapping[str, object],
        live_definition: Mapping[str, object] | None,
        resolved_behavior: ResolvedNodeBehavior,
    ) -> ResolvedNodeBehavior:
        """Return behavior with the default model icon when catalog-backed."""

        if resolved_behavior.card.icon_name is not None:
            return resolved_behavior
        if self._has_explicit_model_picker_field(resolved_behavior):
            return replace(
                resolved_behavior,
                card=replace(resolved_behavior.card, icon_name="model"),
            )
        detector = self._model_backed_node_detector
        if detector is None:
            return resolved_behavior
        if not detector.node_uses_configured_model(
            node_data=node_data,
            live_definition=live_definition,
        ):
            return resolved_behavior
        return replace(
            resolved_behavior,
            card=replace(resolved_behavior.card, icon_name="model"),
        )

    @staticmethod
    def _node_tooltip_from_definition(
        live_definition: Mapping[str, object] | None,
    ) -> str | None:
        """Return normalized node tooltip text from Comfy definition metadata."""

        if not isinstance(live_definition, Mapping):
            return None
        description = live_definition.get("description")
        if not isinstance(description, str):
            return None
        tooltip = description.strip()
        return tooltip or None

    @staticmethod
    def _with_node_tooltip(
        *,
        live_definition: Mapping[str, object] | None,
        resolved_behavior: ResolvedNodeBehavior,
    ) -> ResolvedNodeBehavior:
        """Attach Comfy node description text to the resolved card behavior."""

        tooltip = NodeBehaviorService._node_tooltip_from_definition(live_definition)
        if tooltip is None:
            return resolved_behavior
        return replace(
            resolved_behavior,
            card=replace(resolved_behavior.card, tooltip=tooltip),
        )

    @staticmethod
    def _has_explicit_model_picker_field(
        resolved_behavior: ResolvedNodeBehavior,
    ) -> bool:
        """Return whether resolved behavior contains an explicit model picker field."""

        for field_behavior in resolved_behavior.fields.values():
            model_kind = field_behavior.style.get("model_kind")
            if (
                field_behavior.presentation == FieldPresentation.MODEL_PICKER
                and isinstance(model_kind, str)
                and model_kind.strip()
            ):
                return True
        return False

    @staticmethod
    def _resolve_field_definition(
        *,
        live_definition: Mapping[str, object] | None,
        field_key: str,
    ) -> tuple[str | None, dict[str, object], list[object] | None, dict[str, object]]:
        """Return typed definition metadata for one input field."""

        type_name: str | None = None
        meta_info: dict[str, object] = {}
        field_info: list[object] | None = None
        constraints: dict[str, object] = {"min": None, "max": None, "step": None}

        raw_info = NodeBehaviorService._raw_field_definition(
            live_definition=live_definition,
            field_key=field_key,
        )
        if raw_info is not None:
            field_info = list(raw_info)
            if raw_info:
                if isinstance(raw_info[0], str):
                    type_name = raw_info[0]
                elif isinstance(raw_info[0], Sequence) and not isinstance(
                    raw_info[0],
                    (str, bytes),
                ):
                    type_name = "LIST"
            meta_info = NodeBehaviorService._live_metadata_from_field_info(raw_info)

        if meta_info:
            constraints["min"] = meta_info.get("min")
            constraints["max"] = meta_info.get("max")
            constraints["step"] = meta_info.get("step")
        return type_name, meta_info, field_info, constraints

    @staticmethod
    def _raw_field_definition(
        *,
        live_definition: Mapping[str, object] | None,
        field_key: str,
    ) -> list[object] | None:
        """Return one raw live field definition from required or optional inputs."""

        input_section = (
            live_definition.get("input", {})
            if isinstance(live_definition, Mapping)
            else {}
        )
        if not isinstance(input_section, Mapping):
            return None
        for section_name in ("required", "optional"):
            section = input_section.get(section_name, {})
            if not isinstance(section, Mapping):
                continue
            raw_info = section.get(field_key)
            if isinstance(raw_info, Sequence) and not isinstance(
                raw_info,
                (str, bytes),
            ):
                return list(raw_info)
        return None

    @staticmethod
    def _live_metadata_from_field_info(
        field_info: Sequence[object],
    ) -> dict[str, object]:
        """Return copied metadata from a live Comfy field definition."""

        if len(field_info) < 2 or not isinstance(field_info[1], Mapping):
            return {}
        return deepcopy(dict(field_info[1]))

    def _build_field_specs(
        self,
        *,
        cube_state: CubeStateProtocol,
        alias: str,
        node_name: str,
        class_type: str,
        input_keys: tuple[str, ...],
        node_data: Mapping[str, object],
        live_definition: Mapping[str, object] | None,
        resolved_behavior: ResolvedNodeBehavior,
        is_loaded_cube: bool,
    ) -> dict[str, ResolvedFieldSpec]:
        """Return resolved field specs for one node in render order."""

        node_inputs_raw = node_data.get("inputs")
        node_inputs: Mapping[str, object]
        if isinstance(node_inputs_raw, Mapping):
            node_inputs = {
                key: value
                for key, value in node_inputs_raw.items()
                if isinstance(key, str)
            }
        else:
            node_inputs = {}
        field_specs: dict[str, ResolvedFieldSpec] = {}
        for field_key in input_keys:
            field_behavior = resolved_behavior.fields.get(field_key)
            if field_behavior is None:
                continue
            field_type, meta_info, field_info, constraints = (
                self._resolve_field_definition(
                    live_definition=live_definition,
                    field_key=field_key,
                )
            )
            runtime_meta = dict(meta_info)
            runtime_meta["cube_alias"] = alias
            runtime_meta["node_data"] = dict(node_data)
            raw_value = node_inputs.get(field_key)
            effective_value = raw_value
            value_source = FieldValueSource.EXPLICIT
            has_authored_value = self._has_meaningful_authored_field_value(
                field_key=field_key,
                node_inputs=node_inputs,
                field_type=field_type,
            )
            if not has_authored_value and "default" in meta_info:
                effective_value = meta_info.get("default")
                if meta_info.get("has_authored_default") is True:
                    value_source = FieldValueSource.AUTHORED_DEFAULT
                else:
                    value_source = FieldValueSource.LIVE_DEFAULT
            if is_choice_field_type(field_type):
                runtime_meta["options_resolved"] = bool(
                    extract_live_list_options(field_info)
                )
                runtime_meta["options_unavailable_reason"] = (
                    unresolved_choice_options_reason(field_info)
                )
                pre_choice_value = effective_value
                choice_raw_value = (
                    raw_value
                    if (
                        not has_authored_value
                        and value_source is FieldValueSource.LIVE_DEFAULT
                    )
                    else effective_value
                )
                choice_value, choice_source = self._resolve_effective_list_value(
                    cube_state=cube_state,
                    alias=alias,
                    node_name=node_name,
                    class_type=class_type,
                    field_key=field_key,
                    node_data=node_data,
                    field_type=field_type,
                    field_info=field_info,
                    raw_value=choice_raw_value,
                    allow_canonicalize=(
                        value_source is not FieldValueSource.AUTHORED_DEFAULT
                        and (
                            not (is_loaded_cube and not has_authored_value)
                            or model_kind_for_field(
                                class_type=class_type,
                                input_key=field_key,
                            )
                            is not None
                        )
                    ),
                )
                effective_value = choice_value
                if value_source is FieldValueSource.AUTHORED_DEFAULT:
                    if choice_source is not FieldValueSource.EXPLICIT:
                        effective_value = pre_choice_value
                else:
                    value_source = choice_source
            field_specs[field_key] = ResolvedFieldSpec(
                cube_alias=alias,
                node_name=node_name,
                class_type=class_type,
                field_key=field_key,
                field_type=field_type,
                constraints=constraints,
                meta_info=runtime_meta,
                field_info=field_info,
                value=effective_value,
                raw_value=raw_value,
                value_source=value_source,
                field_behavior=field_behavior,
            )
        return field_specs

    @staticmethod
    def _has_meaningful_authored_field_value(
        *,
        field_key: str,
        node_inputs: Mapping[str, object],
        field_type: str | None,
    ) -> bool:
        """Return whether node inputs contain a meaningful authored render value."""

        if field_key not in node_inputs:
            return False
        value = node_inputs[field_key]
        if isinstance(value, str) and (
            is_choice_field_type(field_type)
            or field_type in {"BOOLEAN", "FLOAT", "INT"}
        ):
            return bool(value.strip())
        return True

    def _resolve_effective_list_value(
        self,
        *,
        cube_state: CubeStateProtocol,
        alias: str,
        node_name: str,
        class_type: str,
        field_key: str,
        node_data: Mapping[str, object],
        field_type: str | None,
        field_info: list[object] | None,
        raw_value: object,
        allow_canonicalize: bool = True,
    ) -> tuple[object, FieldValueSource]:
        """Return the effective value and source for one live list field."""

        field_kind = classify_node_field(
            class_type=class_type,
            field_key=field_key,
            node_data=node_data,
            field_type=field_type,
        )
        if field_kind is NodeFieldKind.LINKED_FIELD:
            return raw_value, FieldValueSource.LINKED
        if field_kind is NodeFieldKind.ASSET_FIELD:
            resolution = resolve_live_list_value(
                raw_value=raw_value,
                field_info=field_info,
                remembered_value=None,
            )
            if resolution is not None and resolution.should_canonicalize:
                log_debug(
                    _LOGGER,
                    "Preserved asset field outside Comfy live options",
                    cube_alias=alias,
                    node_name=node_name,
                    class_type=class_type,
                    field_key=field_key,
                    raw_value=raw_value,
                    field_kind=field_kind.value,
                    would_canonicalize_to=resolution.canonical_value,
                    value_source=resolution.value_source.value,
                )
            return raw_value, FieldValueSource.EXPLICIT

        resolution = resolve_live_list_value(
            raw_value=raw_value,
            field_info=field_info,
            remembered_value=None,
            clear_when_options_empty=True,
        )
        if resolution is None:
            return raw_value, FieldValueSource.EXPLICIT

        if (
            allow_canonicalize
            and resolution.should_canonicalize
            and resolution.canonical_value is not None
        ):
            self._canonicalize_node_input_without_dirty(
                cube_state=cube_state,
                node_name=node_name,
                field_key=field_key,
                canonical_value=resolution.canonical_value,
            )
            log_debug(
                _LOGGER,
                "Canonicalized live list literal from current Comfy options",
                cube_alias=alias,
                node_name=node_name,
                field_key=field_key,
                previous_value=raw_value,
                canonical_value=resolution.canonical_value,
                value_source=resolution.value_source.value,
            )
        return resolution.effective_value, resolution.value_source

    @staticmethod
    def _canonicalize_node_input_without_dirty(
        *,
        cube_state: CubeStateProtocol,
        node_name: str,
        field_key: str,
        canonical_value: str,
    ) -> None:
        """Write one canonical list literal back into the node buffer without dirtying."""

        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, dict):
            return
        nodes = buffer.get("nodes", {})
        if not isinstance(nodes, dict):
            return
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            return
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            return
        previous_dirty = getattr(cube_state, "dirty", None)
        inputs[field_key] = canonical_value
        if isinstance(previous_dirty, bool):
            cube_state.dirty = previous_dirty

    @staticmethod
    def _is_loaded_cube_state(cube_state: CubeStateProtocol) -> bool:
        """Return whether a cube state came from a loaded cube document."""

        ui_payload = getattr(cube_state, "ui", None)
        if isinstance(ui_payload, Mapping) and isinstance(
            ui_payload.get("canonical_cube"),
            Mapping,
        ):
            return True
        original_cube = getattr(cube_state, "original_cube", None)
        return isinstance(original_cube, Mapping)


__all__ = [
    "EditorBehaviorSnapshot",
    "NodeBehaviorRuntimeState",
    "NodeBehaviorService",
]
