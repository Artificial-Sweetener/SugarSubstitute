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
from substitute.domain.cubes import SubgraphWrapperDefinitionIndex
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
    resolve_node_behavior,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
)

from .field_classification import NodeFieldKind, classify_node_field
from .live_definition_authority import (
    LiveNodeDefinitionError,
    LiveNodeFieldDefinition,
    MissingLiveNodeDefinition,
)
from .list_value_resolver import (
    extract_live_list_options,
    is_choice_field_type,
    resolve_live_list_value,
    unresolved_choice_options_reason,
)
from .model_backed_node_detector import ModelBackedNodeDetector
from .models import EditorBehaviorSnapshot, FieldValueSource, ResolvedFieldSpec
from .node_card_order import node_title_for_order, order_node_cards

_LOGGER = get_logger("application.node_behavior.behavior_service")
_WRAPPER_STRUCTURAL_METADATA_KEYS = frozenset(
    {
        "subgraph_wrapper",
        "subgraph_id",
        "interface_id",
        "interface_type",
        "localized_name",
        "label",
        "min",
        "max",
        "step",
        "placeholder",
        "multiline",
        "dynamicPrompts",
        "shape",
        "body_node_type",
        "body_input_name",
        "default_source",
        "has_authored_default",
    }
)
_LIVE_METADATA_FALLBACK_SOURCE = "live_metadata_fallback"


class CubeStateProtocol(Protocol):
    """Describe the cube-state shape consumed by NodeBehaviorService."""

    buffer: dict[str, object]
    ui: dict[str, object]
    dirty: bool


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

        self._node_definition_gateway = node_definition_gateway
        self._model_backed_node_detector = model_backed_node_detector
        self._prompt_endpoint_service = PromptEndpointService()
        self._node_link_endpoint_service = NodeLinkEndpointService()

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
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            layout_nodes = self._layout_nodes(buffer)
            wrapper_definitions = (
                SubgraphWrapperDefinitionIndex.from_runtime_graph(buffer)
                if isinstance(buffer, Mapping)
                else SubgraphWrapperDefinitionIndex.from_runtime_graph({})
            )
            per_node: dict[str, ResolvedNodeBehavior] = {}
            per_node_specs: dict[str, dict[str, ResolvedFieldSpec]] = {}
            for node_name in self._ordered_node_names(nodes, layout_nodes=layout_nodes):
                node_data = nodes.get(node_name)
                if not isinstance(node_data, dict):
                    continue
                class_type = node_data.get("class_type")
                if not isinstance(class_type, str):
                    continue
                node_count += 1
                unique_class_types.add(class_type)
                node_definition_lookup_count += 1
                live_definition = self._lookup_node_definition(
                    class_type=class_type,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=alias,
                    node_name=node_name,
                )
                wrapper_display_name = wrapper_definitions.display_name_for_class_type(
                    class_type
                )
                input_keys = tuple(
                    key
                    for key in self._ordered_input_keys(
                        node_name=node_name,
                        class_type=class_type,
                        node_inputs=node_data.get("inputs", {}),
                        resolved_definition=live_definition,
                    )
                )
                instance_key = f"{alias}:{node_name}"
                context = self._build_node_context(
                    alias=alias,
                    stack_order=stack_order,
                    node_name=node_name,
                    class_type=class_type,
                    node_title=self._node_title(
                        node_name=node_name,
                        node_data=node_data,
                        layout_nodes=layout_nodes,
                    )
                    or wrapper_display_name,
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
                )
                resolved = resolve_node_behavior(
                    node_name=node_name,
                    class_type=class_type,
                    input_keys=input_keys,
                    context=context,
                )
                if self._is_subgraph_wrapper_definition(live_definition):
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
        snapshot = EditorBehaviorSnapshot(
            resolved_nodes_by_alias=resolved_by_alias,
            field_specs_by_alias=field_specs_by_alias,
            prompt_endpoint_index=prompt_endpoint_index,
            node_link_endpoint_index=node_link_endpoint_index,
            card_decisions_by_alias=card_decisions,
            hidden_field_keys_by_alias=hidden_keys,
            reveal_entries_by_alias=reveal_entries,
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
        )

    def _lookup_node_definition(
        self,
        *,
        class_type: str,
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> Mapping[str, object] | None:
        """Return live-only runtime metadata for one class type."""

        lookup_started_at = perf_counter()
        wrapper_definition = wrapper_definitions.definition_for_class_type(class_type)
        if wrapper_definition is not None:
            subgraph_name = wrapper_definitions.display_name_for_class_type(class_type)
            wrapper_definition = self._merge_wrapper_body_live_metadata(
                wrapper_definition,
                wrapper_definitions=wrapper_definitions,
                cube_alias=cube_alias,
                node_name=node_name,
            )
            log_timing(
                _LOGGER,
                "Resolved node definition from subgraph wrapper interface",
                started_at=lookup_started_at,
                level="debug",
                class_type=class_type,
                subgraph_wrapper_definition_available=True,
                subgraph_name=subgraph_name,
            )
            return wrapper_definition

        live_definitions = self._node_definition_gateway.get_node_definition(class_type)
        from_live = (
            live_definitions.get(class_type)
            if isinstance(live_definitions, Mapping)
            else None
        )
        if isinstance(from_live, Mapping):
            log_timing(
                _LOGGER,
                "Resolved node definition from live metadata",
                started_at=lookup_started_at,
                level="debug",
                class_type=class_type,
                live_definition_available=True,
                cube_definition_available=False,
            )
            return from_live
        log_timing(
            _LOGGER,
            "Resolved empty node definition without live metadata",
            started_at=lookup_started_at,
            level="debug",
            class_type=class_type,
            live_definition_available=False,
        )
        return None

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

    def _merge_wrapper_body_live_metadata(
        self,
        wrapper_definition: Mapping[str, object],
        *,
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> Mapping[str, object]:
        """Replace wrapper runtime metadata with linked live body definitions."""

        enriched = deepcopy(dict(wrapper_definition))
        input_section = enriched.get("input")
        if not isinstance(input_section, dict):
            return enriched
        for section_name in ("required", "optional"):
            section = input_section.get(section_name)
            if not isinstance(section, dict):
                continue
            for field_spec in section.values():
                self._merge_wrapper_field_body_live_metadata(
                    field_spec,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=cube_alias,
                    node_name=node_name,
                )
        return enriched

    def _merge_wrapper_field_body_live_metadata(
        self,
        field_spec: object,
        *,
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> None:
        """Replace one mutable wrapper field spec with live body metadata."""

        if (
            not isinstance(field_spec, list)
            or len(field_spec) < 2
            or not isinstance(field_spec[1], dict)
        ):
            return
        metadata = field_spec[1]
        body_node_type = metadata.get("body_node_type")
        body_input_name = metadata.get("body_input_name")
        if not isinstance(body_node_type, str) or not isinstance(
            body_input_name,
            str,
        ):
            return
        live_payload = self._node_definition_gateway.get_required_node_definition(
            body_node_type
        )
        body_definition = (
            live_payload.get(body_node_type)
            if isinstance(live_payload, Mapping)
            else None
        )
        if not isinstance(body_definition, Mapping):
            nested_wrapper_definition = wrapper_definitions.definition_for_class_type(
                body_node_type
            )
            if nested_wrapper_definition is not None:
                body_definition = self._merge_wrapper_body_live_metadata(
                    nested_wrapper_definition,
                    wrapper_definitions=wrapper_definitions,
                    cube_alias=cube_alias,
                    node_name=node_name,
                )
        if not isinstance(body_definition, Mapping):
            raise LiveNodeDefinitionError(
                operation="resolve wrapper body node metadata",
                missing_definitions=(
                    MissingLiveNodeDefinition(
                        class_type=body_node_type,
                        cube_aliases=(cube_alias,),
                        node_names=(node_name,),
                    ),
                ),
            )
        body_field_info = self._raw_field_definition(
            live_definition=body_definition,
            field_key=body_input_name,
        )
        if body_field_info is None:
            raise LiveNodeDefinitionError(
                operation="resolve wrapper body node metadata",
                missing_definitions=(),
                missing_fields=(
                    LiveNodeFieldDefinition(
                        class_type=body_node_type,
                        field_key=body_input_name,
                        field_type=None,
                        meta_info={},
                        field_info=None,
                    ),
                ),
            )
        body_metadata = self._live_metadata_from_field_info(body_field_info)
        body_options = extract_live_list_options(body_field_info)
        if body_options:
            body_metadata = dict(body_metadata)
            body_metadata["options"] = list(body_options)
        structural_metadata = self._wrapper_structural_metadata(metadata)
        replacement_field = deepcopy(body_field_info)
        if not replacement_field:
            return
        if len(replacement_field) < 2 or not isinstance(replacement_field[1], Mapping):
            replacement_field = [replacement_field[0], {}, *replacement_field[1:]]
        replacement_metadata = deepcopy(body_metadata)
        if metadata.get("has_authored_default") is True and "default" in metadata:
            replacement_metadata["default"] = deepcopy(metadata["default"])
            replacement_metadata["default_source"] = metadata.get("default_source")
            replacement_metadata["has_authored_default"] = True
        elif "default" not in replacement_metadata and "default" in metadata:
            replacement_metadata["default"] = deepcopy(metadata["default"])
            replacement_metadata["default_source"] = metadata.get("default_source")
            replacement_metadata["has_authored_default"] = bool(
                metadata.get("has_authored_default")
            )
        else:
            replacement_metadata.setdefault(
                "default_source",
                _LIVE_METADATA_FALLBACK_SOURCE,
            )
            replacement_metadata.setdefault("has_authored_default", False)
        replacement_metadata.update(structural_metadata)
        replacement_field[1] = replacement_metadata
        field_spec[:] = replacement_field

    @staticmethod
    def _wrapper_structural_metadata(
        metadata: dict[str, object],
    ) -> dict[str, object]:
        """Return wrapper-only metadata that is structural rather than runtime."""

        return {
            key: deepcopy(value)
            for key, value in metadata.items()
            if key in _WRAPPER_STRUCTURAL_METADATA_KEYS
        }

    @staticmethod
    def _ordered_input_keys(
        *,
        node_name: str,
        class_type: str,
        node_inputs: object,
        resolved_definition: Mapping[str, object] | None,
    ) -> list[str]:
        """Return definition-owned field order plus persisted extras."""

        _ = node_name, class_type
        present = list(node_inputs.keys()) if isinstance(node_inputs, dict) else []
        definition_input = (
            resolved_definition.get("input", {})
            if isinstance(resolved_definition, Mapping)
            else {}
        )
        definition_keys: list[str] = []
        definition_fields: dict[str, object] = {}
        if isinstance(definition_input, Mapping):
            for section_name in ("required", "optional"):
                section = definition_input.get(section_name, {})
                if isinstance(section, Mapping):
                    definition_fields.update(
                        (key, value)
                        for key, value in section.items()
                        if isinstance(key, str)
                    )
                    definition_keys.extend(
                        key for key in section.keys() if isinstance(key, str)
                    )
        ordered: list[str] = []
        if NodeBehaviorService._is_subgraph_wrapper_definition(resolved_definition):
            for key in definition_keys:
                if (
                    key in present
                    or NodeBehaviorService._definition_field_renders_without_input(
                        definition_fields.get(key)
                    )
                ) and key not in ordered:
                    ordered.append(key)
            for key in present:
                if isinstance(key, str) and key not in ordered:
                    ordered.append(key)
            return ordered
        for key in definition_keys:
            if key not in ordered:
                ordered.append(key)
        for key in present:
            if isinstance(key, str) and key not in ordered:
                ordered.append(key)
        return ordered

    @staticmethod
    def _is_subgraph_wrapper_definition(
        resolved_definition: Mapping[str, object] | None,
    ) -> bool:
        """Return whether the resolved definition describes a wrapper surface node."""

        return bool(
            isinstance(resolved_definition, Mapping)
            and resolved_definition.get("subgraph_wrapper") is True
        )

    @staticmethod
    def _definition_field_renders_without_input(field_definition: object) -> bool:
        """Return whether a wrapper field is renderable without authored input."""

        if (
            not isinstance(field_definition, list)
            or len(field_definition) < 2
            or not isinstance(field_definition[1], Mapping)
        ):
            return False
        return "default" in field_definition[1] or bool(
            extract_live_list_options(field_definition)
        )

    @staticmethod
    def _ordered_node_names(
        nodes: Mapping[str, object],
        *,
        layout_nodes: Mapping[str, object] | None = None,
    ) -> list[str]:
        """Return deterministic node render order matching editor card layout."""

        return order_node_cards(nodes, layout_nodes=layout_nodes)

    @staticmethod
    def _layout_nodes(buffer: Mapping[str, object]) -> Mapping[str, object]:
        """Return cube layout node metadata when present."""

        layout = buffer.get("layout")
        if not isinstance(layout, Mapping):
            return {}
        layout_nodes = layout.get("nodes")
        return layout_nodes if isinstance(layout_nodes, Mapping) else {}

    @staticmethod
    def _node_title(
        *,
        node_name: str,
        node_data: object,
        layout_nodes: Mapping[str, object],
    ) -> str | None:
        """Return the author-facing title for one node using canonical source order."""

        return node_title_for_order(
            node_name=node_name,
            node_data=node_data,
            layout_nodes=layout_nodes,
        )

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
            clear_when_options_empty=(
                model_kind_for_field(
                    class_type=class_type,
                    input_key=field_key,
                )
                is not None
            ),
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
