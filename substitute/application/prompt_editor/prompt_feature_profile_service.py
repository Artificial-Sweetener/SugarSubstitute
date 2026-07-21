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

"""Resolve prompt editor feature profiles from settings, fields, and workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from substitute.domain.prompt.features import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptFeatureDisabledReason,
)
from substitute.shared.logging.logger import get_logger, log_debug
from substitute.shared.startup_trace import trace_span

from .prompt_editor_preference_service import PromptEditorPreferenceService
from .prompt_feature_registry import (
    PromptFeatureDefinition,
    prompt_feature_definitions,
    prompt_syntax_field_features,
)

if TYPE_CHECKING:
    from .effective_scheduled_lora_provider import WorkflowPromptContext

_LOGGER = get_logger("application.prompt_editor.feature_profile_service")
_PROMPT_FEATURES_STYLE_KEY = "prompt_features"
_PROMPT_SYNTAXES_STYLE_KEY = "prompt_syntaxes"
_PROMPT_CONTROL_TEXT_ENCODER_PREFIXES = (
    "PCLazyTextEncode",
    "PCTextEncode",
)
_SIMPLE_SYRUP_SCHEDULE_AND_ENCODE_CLASS = (
    "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
)
_PROMPT_CONTROL_LORA_PROMPT_INPUTS = frozenset(
    {
        "positive_prompt",
        "negative_prompt",
    }
)
_RUNTIME_LORA_PROMPT_FEATURES = frozenset(
    {
        PromptEditorFeature.LORA_AUTOCOMPLETE,
        PromptEditorFeature.LORA_PICKER,
        PromptEditorFeature.LORA_TRIGGER_WORDS,
    }
)


class PromptFeatureProfileService:
    """Build final prompt editor feature profiles for prompt fields."""

    def __init__(
        self,
        *,
        preference_service: PromptEditorPreferenceService,
    ) -> None:
        """Store collaborators used by feature profile resolution."""

        self._preference_service = preference_service

    def build_profile(
        self,
        *,
        field_style: Mapping[str, object],
        workflow_context: WorkflowPromptContext | None,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptEditorFeatureProfile:
        """Resolve the final prompt editor feature profile for one prompt field."""

        trace_context = {
            "cube_alias": cube_alias or "",
            "prompt_node_name": prompt_node_name,
            "prompt_field_key": prompt_field_key,
            "workflow_context_present": workflow_context is not None,
        }
        with trace_span(
            "prompt_feature_profile.load_preferences",
            **trace_context,
        ):
            user_preferences = self._preference_service.load_preferences()
        with trace_span(
            "prompt_feature_profile.field_allowed_features",
            **trace_context,
        ):
            field_allowed = self._field_allowed_features(field_style)
        decisions: dict[PromptEditorFeature, PromptFeatureDecision] = {}
        definitions = prompt_feature_definitions()
        with trace_span(
            "prompt_feature_profile.base_decisions",
            field_allowed_count=len(field_allowed),
            **trace_context,
        ):
            for definition in definitions:
                decision = self._base_decision(
                    definition=definition,
                    field_allowed=field_allowed,
                    user_allows=user_preferences.user_allows(definition.feature),
                )
                decisions[definition.feature] = decision
        with trace_span(
            "prompt_feature_profile.apply_dependencies",
            **trace_context,
        ):
            self._apply_dependencies(decisions)
        with trace_span(
            "prompt_feature_profile.apply_runtime_capabilities",
            **trace_context,
        ):
            self._apply_runtime_capabilities(
                decisions,
                workflow_context=workflow_context,
                cube_alias=cube_alias,
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
            )
        with trace_span(
            "prompt_feature_profile.apply_conflicts",
            **trace_context,
        ):
            self._apply_conflicts(
                decisions,
                cube_alias=cube_alias,
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
            )
        with trace_span(
            "prompt_feature_profile.build_result",
            enabled_count=sum(1 for decision in decisions.values() if decision.enabled),
            **trace_context,
        ):
            return PromptEditorFeatureProfile(
                decisions=tuple(
                    decisions[definition.feature] for definition in definitions
                )
            )

    def renderer_syntax_profile(
        self,
        profile: PromptEditorFeatureProfile,
    ) -> tuple[str, ...]:
        """Return renderer syntax kinds enabled by a feature profile."""

        syntax_kinds: list[str] = []
        for definition in prompt_feature_definitions():
            if not profile.supports(definition.feature):
                continue
            for syntax_kind in definition.renderer_syntax_kinds:
                if syntax_kind not in syntax_kinds:
                    syntax_kinds.append(syntax_kind)
        return tuple(syntax_kinds)

    def build_library_profile(self) -> PromptEditorFeatureProfile:
        """Resolve preference-controlled features without workflow capability gates."""

        user_preferences = self._preference_service.load_preferences()
        decisions = {
            definition.feature: PromptFeatureDecision(
                feature=definition.feature,
                enabled=user_preferences.user_allows(definition.feature),
                disabled_reason=(
                    None
                    if user_preferences.user_allows(definition.feature)
                    else PromptFeatureDisabledReason.USER_DISABLED
                ),
            )
            for definition in prompt_feature_definitions()
        }
        self._apply_dependencies(decisions)
        self._apply_conflicts(
            decisions,
            cube_alias=None,
            prompt_node_name="wildcard-library",
            prompt_field_key="wildcard-value",
        )
        return PromptEditorFeatureProfile(
            decisions=tuple(
                decisions[definition.feature]
                for definition in prompt_feature_definitions()
            )
        )

    def _field_allowed_features(
        self,
        field_style: Mapping[str, object],
    ) -> frozenset[PromptEditorFeature]:
        """Return features allowed by prompt field style metadata."""

        explicit_features = self._features_from_prompt_features(field_style)
        if explicit_features is not None:
            return explicit_features
        syntax_features = self._features_from_prompt_syntaxes(field_style)
        if syntax_features is not None:
            return syntax_features
        return frozenset(
            definition.feature for definition in prompt_feature_definitions()
        )

    def _features_from_prompt_features(
        self,
        field_style: Mapping[str, object],
    ) -> frozenset[PromptEditorFeature] | None:
        """Resolve explicit `prompt_features` metadata when present."""

        raw_features = field_style.get(_PROMPT_FEATURES_STYLE_KEY)
        if not isinstance(raw_features, list):
            return None
        features: set[PromptEditorFeature] = set()
        for entry in raw_features:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip().lower()
            try:
                features.add(PromptEditorFeature(normalized))
            except ValueError:
                continue
        return frozenset(features)

    def _features_from_prompt_syntaxes(
        self,
        field_style: Mapping[str, object],
    ) -> frozenset[PromptEditorFeature] | None:
        """Resolve legacy `prompt_syntaxes` metadata when present."""

        raw_syntaxes = field_style.get(_PROMPT_SYNTAXES_STYLE_KEY)
        if not isinstance(raw_syntaxes, list):
            return None
        return prompt_syntax_field_features(raw_syntaxes)

    def _base_decision(
        self,
        *,
        definition: PromptFeatureDefinition,
        field_allowed: frozenset[PromptEditorFeature],
        user_allows: bool,
    ) -> PromptFeatureDecision:
        """Return the first-pass decision for one feature."""

        if definition.feature not in field_allowed:
            return PromptFeatureDecision(
                feature=definition.feature,
                enabled=False,
                disabled_reason=PromptFeatureDisabledReason.FIELD_DISABLED,
            )
        if not user_allows:
            return PromptFeatureDecision(
                feature=definition.feature,
                enabled=False,
                disabled_reason=PromptFeatureDisabledReason.USER_DISABLED,
            )
        return PromptFeatureDecision(feature=definition.feature, enabled=True)

    def _apply_dependencies(
        self,
        decisions: dict[PromptEditorFeature, PromptFeatureDecision],
    ) -> None:
        """Disable features whose dependencies are disabled."""

        changed = True
        while changed:
            changed = False
            for definition in prompt_feature_definitions():
                decision = decisions[definition.feature]
                if not decision.enabled:
                    continue
                for dependency in definition.dependencies:
                    dependency_decision = decisions[dependency]
                    if dependency_decision.enabled:
                        continue
                    decisions[definition.feature] = PromptFeatureDecision(
                        feature=definition.feature,
                        enabled=False,
                        disabled_reason=dependency_decision.disabled_reason,
                        detail=f"Requires {dependency.value}.",
                    )
                    changed = True
                    break

    def _apply_runtime_capabilities(
        self,
        decisions: dict[PromptEditorFeature, PromptFeatureDecision],
        *,
        workflow_context: WorkflowPromptContext | None,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> None:
        """Disable LoRA runtime actions absent proven Prompt Control support."""

        if self._supports_prompt_control_lora(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        ):
            return
        for feature in _RUNTIME_LORA_PROMPT_FEATURES:
            decision = decisions[feature]
            if not decision.enabled:
                continue
            decisions[feature] = PromptFeatureDecision(
                feature=feature,
                enabled=False,
                disabled_reason=PromptFeatureDisabledReason.MISSING_SERVICE,
                detail=(
                    "Prompt Control LoRA scheduling is not available for this "
                    "prompt field."
                ),
            )
            log_debug(
                _LOGGER,
                "Disabled Prompt Control LoRA prompt feature without runtime support",
                cube_alias=cube_alias or "",
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
                disabled_feature=feature.value,
            )

    def _supports_prompt_control_lora(
        self,
        *,
        workflow_context: WorkflowPromptContext | None,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> bool:
        """Return whether a cube proves Prompt Control LoRA prompt support."""

        if workflow_context is None or cube_alias is None:
            return False
        return any(
            self._graph_supports_prompt_control_lora(
                cube_graph=cube_graph,
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
            )
            for cube_graph in _cube_graphs(workflow_context.cube_states.get(cube_alias))
        )

    def _graph_supports_prompt_control_lora(
        self,
        *,
        cube_graph: Mapping[str, object],
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> bool:
        """Return whether one cube graph proves Prompt Control LoRA support."""

        nodes = _graph_nodes(cube_graph)
        prompt_node = nodes.get(prompt_node_name)
        if _node_supports_prompt_control_lora_field(
            prompt_node,
            prompt_field_key=prompt_field_key,
        ):
            return True
        return any(
            self._node_supports_prompt_control_lora_from_source(
                node=node,
                cube_graph=cube_graph,
                source_node_name=prompt_node_name,
            )
            for node in nodes.values()
        )

    def _node_supports_prompt_control_lora_from_source(
        self,
        *,
        node: Mapping[str, object],
        cube_graph: Mapping[str, object],
        source_node_name: str,
    ) -> bool:
        """Return whether a node consumes source prompt text through LoRA inputs."""

        return any(
            _node_supports_prompt_control_lora_input(
                node,
                cube_graph=cube_graph,
                input_key=input_key,
            )
            for input_key in _node_input_keys_consuming_output(
                node,
                source_node_name=source_node_name,
            )
        )

    def _apply_conflicts(
        self,
        decisions: dict[PromptEditorFeature, PromptFeatureDecision],
        *,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> None:
        """Disable lower-priority features that conflict with enabled features."""

        for definition in prompt_feature_definitions():
            decision = decisions[definition.feature]
            if not decision.enabled:
                continue
            for conflict in definition.conflicts_with:
                conflict_decision = decisions.get(conflict)
                if conflict_decision is None or not conflict_decision.enabled:
                    continue
                decisions[conflict] = PromptFeatureDecision(
                    feature=conflict,
                    enabled=False,
                    disabled_reason=PromptFeatureDisabledReason.CONFLICT,
                    detail=f"Conflicts with {definition.feature.value}.",
                )
                log_debug(
                    _LOGGER,
                    "Disabled conflicting prompt editor feature",
                    cube_alias=cube_alias,
                    prompt_node_name=prompt_node_name,
                    prompt_field_key=prompt_field_key,
                    kept_feature=definition.feature.value,
                    disabled_feature=conflict.value,
                )


def wildcard_management_prompt_feature_profile() -> PromptEditorFeatureProfile:
    """Return registry-backed default features for wildcard file authoring."""

    return PromptEditorFeatureProfile(
        decisions=tuple(
            PromptFeatureDecision(
                feature=definition.feature,
                enabled=definition.default_user_allowed,
            )
            for definition in prompt_feature_definitions()
        )
    )


def _cube_graphs(cube_state: object) -> tuple[Mapping[str, object], ...]:
    """Return candidate cube graphs from live and restored cube state."""

    graphs: list[Mapping[str, object]] = []
    buffer = getattr(cube_state, "buffer", None)
    if isinstance(buffer, Mapping):
        graphs.append(buffer)
    original_cube = getattr(cube_state, "original_cube", None)
    if isinstance(original_cube, Mapping) and original_cube is not buffer:
        graphs.append(original_cube)
    return tuple(graphs)


def _graph_nodes(cube_graph: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """Return authored cube nodes keyed by node name."""

    raw_nodes = cube_graph.get("nodes")
    if not isinstance(raw_nodes, Mapping):
        return {}
    return {
        str(node_name): node
        for node_name, node in raw_nodes.items()
        if isinstance(node, Mapping)
    }


def _node_class_type(node: Mapping[str, object] | None) -> str:
    """Return the normalized class type from an authored cube node."""

    if node is None:
        return ""
    class_type = node.get("class_type") or node.get("type")
    return class_type.strip() if isinstance(class_type, str) else ""


def _node_uses_prompt_control_text_encoder(
    node: Mapping[str, object] | None,
) -> bool:
    """Return whether one node is itself a Prompt Control text encoder."""

    return _is_prompt_control_text_encoder_class(_node_class_type(node))


def _node_supports_prompt_control_lora_field(
    node: Mapping[str, object] | None,
    *,
    prompt_field_key: str,
) -> bool:
    """Return whether a node's own prompt field supports Prompt Control LoRA tags."""

    if node is None:
        return False
    if _node_uses_prompt_control_text_encoder(node):
        return True
    class_type = _node_class_type(node)
    return (
        class_type == _SIMPLE_SYRUP_SCHEDULE_AND_ENCODE_CLASS
        and prompt_field_key in _PROMPT_CONTROL_LORA_PROMPT_INPUTS
    )


def _is_prompt_control_text_encoder_class(class_type: str) -> bool:
    """Return whether a class type is a Prompt Control text encoder."""

    return any(
        class_type.startswith(prefix)
        for prefix in _PROMPT_CONTROL_TEXT_ENCODER_PREFIXES
    )


def _node_supports_prompt_control_lora_input(
    node: Mapping[str, object],
    *,
    cube_graph: Mapping[str, object],
    input_key: str,
) -> bool:
    """Return whether one node input accepts Prompt Control LoRA prompt text."""

    class_type = _node_class_type(node)
    if _is_prompt_control_text_encoder_class(class_type):
        return True
    if class_type == _SIMPLE_SYRUP_SCHEDULE_AND_ENCODE_CLASS:
        return input_key in _PROMPT_CONTROL_LORA_PROMPT_INPUTS
    return (
        input_key in _PROMPT_CONTROL_LORA_PROMPT_INPUTS
        and _subgraph_wrapper_supports_prompt_control_lora(
            cube_graph=cube_graph,
            class_type=class_type,
        )
    )


def _node_input_keys_consuming_output(
    node: Mapping[str, object],
    *,
    source_node_name: str,
) -> tuple[str, ...]:
    """Return input keys linked from a source node output."""

    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return ()
    return tuple(
        str(input_key)
        for input_key, value in inputs.items()
        if _link_source_name(value) == source_node_name
    )


def _link_source_name(value: object) -> str | None:
    """Return the source node name for a serialized two-item link."""

    if (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes)
        and len(value) == 2
        and isinstance(value[0], str)
    ):
        return value[0]
    return None


def _subgraph_wrapper_supports_prompt_control_lora(
    *,
    cube_graph: Mapping[str, object],
    class_type: str,
) -> bool:
    """Return whether a subgraph wrapper body contains Prompt Control text encoding."""

    if not class_type:
        return False
    subgraphs = cube_graph.get("subgraphs")
    if not isinstance(subgraphs, Sequence) or isinstance(subgraphs, str | bytes):
        return False
    for subgraph in subgraphs:
        if not isinstance(subgraph, Mapping) or subgraph.get("id") != class_type:
            continue
        nodes = subgraph.get("nodes")
        if not isinstance(nodes, Sequence) or isinstance(nodes, str | bytes):
            return False
        return any(
            isinstance(node, Mapping) and _node_uses_prompt_control_text_encoder(node)
            for node in nodes
        )
    return False


__all__ = ["PromptFeatureProfileService", "wildcard_management_prompt_feature_profile"]
