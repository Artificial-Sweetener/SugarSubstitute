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

"""Serialize typed recipe state into deterministic Sugar DSL text."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Callable, Protocol, TypeVar

from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonValue,
)
from substitute.domain.generation.seed_control import SeedControlState
from substitute.domain.generation.seed_control import SeedMode
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.recipes.recipe_buffers import recipe_buffer_update_policy
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.recipes.sugar_literal_codec import SugarLiteralCodec
from substitute.domain.recipes.sugar_links import node_reference
from substitute.domain.recipes.sugar_path_codec import SugarPathCodec
from substitute.domain.workflow.override_keys import canonicalize_global_override_key

_UNQUOTED_VERSION_PIN_PATTERN = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")
_SHA256_COMMENT_RE = re.compile(r"^#\s*sha256\s+([A-Fa-f0-9]{64})\s*$")
_SHA256_VALUE_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
_LORA_SHA256_COMMENT_PREFIX = "# lora_sha256 "
_LITERAL_CODEC = SugarLiteralCodec()
_PATH_CODEC = SugarPathCodec()
_T = TypeVar("_T")


class SugarScriptLabelResolver(Protocol):
    """Describe script-label resolution required during serialization."""

    def node_label_for(self, alias: str, node_key: str) -> str:
        """Return the script-visible node label for one machine key."""

        ...

    def input_label_for(self, alias: str, node_key: str, input_key: str) -> str:
        """Return the script-visible input label for one machine key."""

        ...

    def global_input_label_for(
        self,
        input_key: str,
        participant_fields: Iterable[tuple[str, str, str]],
    ) -> str:
        """Return the script-visible wildcard input label."""

        ...

    def endpoint_label_for(self, alias: str, endpoint_key: JsonValue) -> JsonValue:
        """Return the script-visible connect endpoint label."""

        ...


class SugarScriptSerializationError(ValueError):
    """Report invalid state at the Sugar serialization boundary."""


@dataclass(frozen=True)
class SugarScriptSerializationRequest:
    """Carry all state required for one deterministic Sugar serialization."""

    buffers: Mapping[str, Mapping[str, JsonValue]]
    ordered_aliases: tuple[str, ...]
    global_overrides: GlobalOverrideMap = field(default_factory=dict)
    global_override_selections: GlobalOverrideSelectionMap = field(default_factory=dict)
    enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None
    disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None = None
    global_override_scopes: Mapping[str, GlobalOverrideSerializationScope] | None = None
    label_resolver: SugarScriptLabelResolver | None = None
    model_hashes_by_field: Mapping[tuple[str, str, str], str] | None = None
    prompt_lora_hashes_by_field: (
        Mapping[tuple[str, str, str], Mapping[str, str]] | None
    ) = None
    field_control_states_by_alias: (
        Mapping[str, Mapping[str, Mapping[str, SeedControlState]]] | None
    ) = None
    override_control_states: Mapping[str, SeedControlState] | None = None


@dataclass
class _SerializationState:
    """Collect ordered statement sections during one serialization."""

    use_lines: list[str] = field(default_factory=list)
    global_override_lines: list[str] = field(default_factory=list)
    global_override_value_lines: list[str] = field(default_factory=list)
    global_override_selection_lines: list[str] = field(default_factory=list)
    seed_control_lines: list[str] = field(default_factory=list)
    global_override_seed_control_lines: list[str] = field(default_factory=list)
    reveal_metadata_lines: list[str] = field(default_factory=list)
    enabled_metadata_lines: list[str] = field(default_factory=list)
    output_persistence_lines: list[str] = field(default_factory=list)
    enable_lines: list[str] = field(default_factory=list)
    disable_lines: list[str] = field(default_factory=list)
    set_blocks: list[str] = field(default_factory=list)
    connect_lines: list[str] = field(default_factory=list)
    alias_tokens: dict[str, str] = field(default_factory=dict)
    alias_bypassed: dict[str, bool] = field(default_factory=dict)
    partial_scope_values_by_field: dict[tuple[str, str, str], JsonValue] = field(
        default_factory=dict
    )
    full_scope_keys: frozenset[str] = frozenset()


class SugarScriptSerializer:
    """Own Sugar statement construction, ordering, and section assembly."""

    def serialize(self, request: SugarScriptSerializationRequest) -> str:
        """Return deterministic Sugar script text for one typed request."""

        self._validate_request(request)
        state = _SerializationState()
        self._write_use_statements(request, state)
        self._write_output_persistence_metadata(request, state)
        self._write_override_statements(request, state)
        self._write_control_metadata(request, state)
        self._write_activation_statements(request, state)
        self._write_set_statements(request, state)
        self._write_connection_statements(request, state)
        return self._assemble_sections(state)

    def _validate_request(self, request: SugarScriptSerializationRequest) -> None:
        """Reject incomplete stack state before emitting a partial script."""

        seen_aliases: set[str] = set()
        for alias in request.ordered_aliases:
            if alias in seen_aliases:
                raise SugarScriptSerializationError(
                    f"Sugar serialization contains duplicate alias '{alias}'."
                )
            seen_aliases.add(alias)
            buffer = request.buffers.get(alias)
            if buffer is None:
                raise SugarScriptSerializationError(
                    f"Sugar serialization is missing buffer for alias '{alias}'."
                )
            cube_id = buffer.get("cube_id")
            if not isinstance(cube_id, str) or not cube_id.strip():
                raise SugarScriptSerializationError(
                    f"Sugar serialization alias '{alias}' has no cube ID."
                )

    def _write_use_statements(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Write cube declarations and cache their script identities."""

        for alias in request.ordered_aliases:
            alias_token = _PATH_CODEC.encode_segment(alias)
            buffer = request.buffers[alias]
            bypassed = _is_buffer_bypassed(buffer)
            use_target = _format_use_target(
                str(buffer["cube_id"]),
                _version_pin_from_buffer(buffer),
            )
            state.use_lines.append(
                _bypass_statement(f"use {use_target} as {alias_token}", bypassed)
            )
            state.alias_tokens[alias] = alias_token
            state.alias_bypassed[alias] = bypassed

    def _write_output_persistence_metadata(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Persist workflow-local memory-only cube output policy as metadata."""

        for alias in request.ordered_aliases:
            if request.buffers[alias].get("save_outputs") is not False:
                continue
            payload = json.dumps(
                {"alias": alias, "saved": False}, separators=(",", ":")
            )
            state.output_persistence_lines.append(
                f"# cube_output_persistence {payload}"
            )

    def _write_override_statements(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Write wildcard overrides and partial-scope persistence metadata."""

        scopes = request.global_override_scopes
        if scopes is not None:
            state.full_scope_keys = frozenset(
                canonicalize_global_override_key(scope.override_key)
                for scope in scopes.values()
                if scope.full_participation
            )
            for scope in scopes.values():
                override_key = canonicalize_global_override_key(scope.override_key)
                override_label = _global_input_label_for_script(
                    label_resolver=request.label_resolver,
                    input_key=override_key,
                    participant_fields=scope.participant_fields,
                )
                if scope.full_participation:
                    state.global_override_lines.append(
                        f"set *.*.{_PATH_CODEC.encode_segment(override_label)} = "
                        f"{_LITERAL_CODEC.encode(scope.value)}"
                    )
                    continue
                state.global_override_value_lines.append(
                    "# global_override_value "
                    + json.dumps(
                        {
                            "key": override_key,
                            "mode": scope.mode or "global",
                            "value": scope.value,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                for alias, node_name, field_key in scope.participant_fields:
                    state.partial_scope_values_by_field[
                        (str(alias), str(node_name), str(field_key))
                    ] = scope.value
        elif request.global_overrides:
            for field_key, override in request.global_overrides.items():
                if not isinstance(override, dict):
                    continue
                override_key = canonicalize_global_override_key(str(field_key))
                override_label = _global_input_label_for_script(
                    label_resolver=request.label_resolver,
                    input_key=override_key,
                    participant_fields=(),
                )
                state.global_override_lines.append(
                    f"set *.*.{_PATH_CODEC.encode_segment(override_label)} = "
                    f"{_LITERAL_CODEC.encode(override.get('value'))}"
                )

        for field_key, selected in sorted(request.global_override_selections.items()):
            if not isinstance(selected, bool):
                continue
            state.global_override_selection_lines.append(
                "# global_override_selection "
                + json.dumps(
                    {
                        "key": canonicalize_global_override_key(str(field_key)),
                        "selected": selected,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )

    def _write_control_metadata(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Write fixed seed-control state as deterministic metadata."""

        if request.field_control_states_by_alias:
            state.seed_control_lines.extend(
                _seed_control_metadata_lines(
                    ordered_aliases=list(request.ordered_aliases),
                    field_control_states_by_alias=request.field_control_states_by_alias,
                    label_resolver=request.label_resolver,
                )
            )
        if request.override_control_states:
            state.global_override_seed_control_lines.extend(
                _global_override_seed_control_metadata_lines(
                    request.override_control_states,
                    request.label_resolver,
                )
            )

    def _write_activation_statements(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Write reveal metadata and executable activation deltas."""

        overrides_provided = (
            request.enabled_node_keys_by_alias is not None
            or request.disabled_node_keys_by_alias is not None
        )
        for alias in request.ordered_aliases:
            nodes = request.buffers[alias].get("nodes", {})
            if not isinstance(nodes, dict):
                continue
            bypassed = state.alias_bypassed[alias]
            alias_token = state.alias_tokens[alias]
            enabled_names = _enabled_node_names_for_alias(
                alias=alias,
                enabled_node_keys_by_alias=request.enabled_node_keys_by_alias,
            )
            disabled_names = _disabled_node_names_for_alias(
                alias=alias,
                disabled_node_keys_by_alias=request.disabled_node_keys_by_alias,
            )
            for node_name, node in nodes.items():
                if not isinstance(node, dict):
                    continue
                node_key = str(node_name)
                node_enabled = _resolved_node_enabled(
                    node_name=node_key,
                    node=node,
                    enabled_node_names=enabled_names,
                    disabled_node_names=disabled_names,
                    activation_overrides_provided=overrides_provided,
                )
                command = _node_activation_command(
                    node=node,
                    node_enabled=node_enabled,
                )
                node_label = _node_label_for_script(
                    label_resolver=request.label_resolver,
                    alias=alias,
                    node_key=node_key,
                )
                if node.get("revealed") is True and not overrides_provided:
                    state.reveal_metadata_lines.append(
                        _bypass_statement(
                            "# node_revealed "
                            + json.dumps(
                                {"alias": alias, "node": node_key},
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            bypassed,
                        )
                    )
                if (
                    node.get("enabled") is True
                    and not overrides_provided
                    and command is None
                ):
                    state.enabled_metadata_lines.append(
                        _bypass_statement(
                            "# node_enabled "
                            + json.dumps(
                                {"alias": alias, "enabled": True, "node": node_key},
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            bypassed,
                        )
                    )
                if command == "enable":
                    state.enable_lines.append(
                        _bypass_statement(
                            f"enable {alias_token}."
                            f"{_PATH_CODEC.encode_segment(node_label)}",
                            bypassed,
                        )
                    )
                elif command == "disable":
                    state.disable_lines.append(
                        _bypass_statement(
                            f"disable {alias_token}."
                            f"{_PATH_CODEC.encode_segment(node_label)}",
                            bypassed,
                        )
                    )

    def _write_set_statements(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Write enabled node links and literal input assignments."""

        overrides_provided = (
            request.enabled_node_keys_by_alias is not None
            or request.disabled_node_keys_by_alias is not None
        )
        for alias in request.ordered_aliases:
            nodes = request.buffers[alias].get("nodes", {})
            if not isinstance(nodes, dict):
                continue
            set_lines: list[str] = []
            enabled_names = _enabled_node_names_for_alias(
                alias=alias,
                enabled_node_keys_by_alias=request.enabled_node_keys_by_alias,
            )
            disabled_names = _disabled_node_names_for_alias(
                alias=alias,
                disabled_node_keys_by_alias=request.disabled_node_keys_by_alias,
            )
            for node_name, node in _ordered_script_node_items(nodes):
                if not isinstance(node, dict):
                    continue
                node_key = str(node_name)
                if not _resolved_node_enabled(
                    node_name=node_key,
                    node=node,
                    enabled_node_names=enabled_names,
                    disabled_node_names=disabled_names,
                    activation_overrides_provided=overrides_provided,
                ):
                    continue
                node_label = _node_label_for_script(
                    label_resolver=request.label_resolver,
                    alias=alias,
                    node_key=node_key,
                )
                node_link = _active_node_link(node) or _legacy_prompt_node_link(
                    node, node_key
                )
                if node_link is not None:
                    set_lines.append(
                        f"set {state.alias_tokens[alias]}."
                        f"{_PATH_CODEC.encode_segment(node_label)} = "
                        f"{_node_reference_for_script(request.label_resolver, node_link)}"
                    )
                inputs = node.get("inputs", {})
                if not isinstance(inputs, dict):
                    continue
                for input_key, value in _ordered_script_input_items(inputs):
                    self._write_input_statement(
                        request=request,
                        state=state,
                        set_lines=set_lines,
                        alias=alias,
                        node=node,
                        node_key=node_key,
                        node_label=node_label,
                        input_key=str(input_key),
                        value=value,
                    )
            if set_lines:
                state.set_blocks.append(
                    _bypass_statement(
                        "\n".join(set_lines),
                        state.alias_bypassed[alias],
                    )
                )

    def _write_input_statement(
        self,
        *,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
        set_lines: list[str],
        alias: str,
        node: Mapping[str, JsonValue],
        node_key: str,
        node_label: str,
        input_key: str,
        value: JsonValue,
    ) -> None:
        """Write one field assignment or skip it when an override owns the field."""

        override_key = canonicalize_global_override_key(input_key)
        field_identity = (alias, node_key, input_key)
        input_label = _input_label_for_script(
            label_resolver=request.label_resolver,
            alias=alias,
            node_key=node_key,
            input_key=input_key,
        )
        if request.global_override_scopes is None:
            if request.global_overrides and input_key in request.global_overrides:
                return
        else:
            if override_key in state.full_scope_keys:
                return
            if field_identity in state.partial_scope_values_by_field:
                self._append_literal_assignment(
                    request=request,
                    set_lines=set_lines,
                    field_identity=field_identity,
                    alias_token=state.alias_tokens[alias],
                    node_label=node_label,
                    input_label=input_label,
                    value=state.partial_scope_values_by_field[field_identity],
                )
                return

        linked_field = None
        linked_input_key = None
        if input_key == "sampler_name":
            linked_field = node.get("sampler_link")
            linked_input_key = "sampler_name"
        elif input_key == "scheduler":
            linked_field = node.get("scheduler_link")
            linked_input_key = "scheduler"
        if (
            isinstance(linked_field, dict)
            and linked_input_key is not None
            and "from_cube" in linked_field
            and "from_node" in linked_field
        ):
            link_reference = _field_reference_for_script(
                label_resolver=request.label_resolver,
                alias=str(linked_field["from_cube"]),
                node_key=str(linked_field["from_node"]),
                input_key=linked_input_key,
            )
            set_lines.append(
                self._assignment_prefix(
                    state.alias_tokens[alias],
                    node_label,
                    input_label,
                )
                + link_reference
            )
            _append_model_hash_comment(
                set_lines,
                field_identity=field_identity,
                model_hashes_by_field=request.model_hashes_by_field,
            )
            _append_prompt_lora_hash_comments(
                set_lines,
                field_identity=field_identity,
                prompt_lora_hashes_by_field=request.prompt_lora_hashes_by_field,
            )
            return

        if isinstance(value, (list, dict)):
            return
        self._append_literal_assignment(
            request=request,
            set_lines=set_lines,
            field_identity=field_identity,
            alias_token=state.alias_tokens[alias],
            node_label=node_label,
            input_label=input_label,
            value=value,
        )

    def _append_literal_assignment(
        self,
        *,
        request: SugarScriptSerializationRequest,
        set_lines: list[str],
        field_identity: tuple[str, str, str],
        alias_token: str,
        node_label: str,
        input_label: str,
        value: JsonValue,
    ) -> None:
        """Append one literal assignment and its adjacent integrity metadata."""

        set_lines.append(
            self._assignment_prefix(alias_token, node_label, input_label)
            + _LITERAL_CODEC.encode(value)
        )
        _append_model_hash_comment(
            set_lines,
            field_identity=field_identity,
            model_hashes_by_field=request.model_hashes_by_field,
        )
        if isinstance(value, str):
            _append_prompt_lora_hash_comments(
                set_lines,
                field_identity=field_identity,
                prompt_lora_hashes_by_field=request.prompt_lora_hashes_by_field,
            )

    def _assignment_prefix(
        self,
        alias_token: str,
        node_label: str,
        input_label: str,
    ) -> str:
        """Return the left side and equals token for one field assignment."""

        return (
            f"set {alias_token}.{_PATH_CODEC.encode_segment(node_label)}."
            f"{_PATH_CODEC.encode_segment(input_label)} = "
        )

    def _write_connection_statements(
        self,
        request: SugarScriptSerializationRequest,
        state: _SerializationState,
    ) -> None:
        """Connect adjacent active cubes using their public endpoints."""

        active_aliases = [
            alias
            for alias in request.ordered_aliases
            if not state.alias_bypassed[alias]
        ]
        for index in range(len(active_aliases) - 1):
            from_alias = active_aliases[index]
            to_alias = active_aliases[index + 1]
            from_outputs = request.buffers[from_alias].get("outputs", {})
            to_inputs = request.buffers[to_alias].get("inputs", {})
            if not isinstance(from_outputs, dict) or not isinstance(to_inputs, dict):
                continue
            for from_output in from_outputs:
                endpoint_from = format_connect_endpoint(
                    state.alias_tokens[from_alias],
                    _endpoint_label_for_script(
                        label_resolver=request.label_resolver,
                        alias=from_alias,
                        endpoint_key=from_output,
                    ),
                )
                for to_input in to_inputs:
                    endpoint_to = format_connect_endpoint(
                        state.alias_tokens[to_alias],
                        _endpoint_label_for_script(
                            label_resolver=request.label_resolver,
                            alias=to_alias,
                            endpoint_key=to_input,
                        ),
                    )
                    state.connect_lines.append(
                        f"connect {endpoint_from} to {endpoint_to}"
                    )

    def _assemble_sections(self, state: _SerializationState) -> str:
        """Join non-empty sections in the persisted Sugar document order."""

        sections = [
            "\n".join(state.use_lines),
            "\n".join(state.output_persistence_lines),
            "\n".join(state.global_override_lines),
            "\n".join(state.global_override_value_lines),
            "\n".join(state.global_override_selection_lines),
            "\n".join(state.seed_control_lines),
            "\n".join(state.global_override_seed_control_lines),
            "\n".join(state.reveal_metadata_lines),
            "\n".join(state.enabled_metadata_lines),
            "\n".join(state.enable_lines),
            "\n".join(state.disable_lines),
            *state.set_blocks,
        ]
        if state.connect_lines:
            sections.append("\n".join(state.connect_lines))
        return "\n\n".join(section for section in sections if section) + "\n"


def _format_version_pin(version: str) -> str:
    """Return a Sugar parser-compatible version pin literal."""

    if _UNQUOTED_VERSION_PIN_PATTERN.fullmatch(version):
        return version
    return _LITERAL_CODEC.encode(version)


def _version_pin_from_buffer(buffer_data: Mapping[str, JsonValue]) -> str | None:
    """Return the pinned cube version to serialize, or None for follow-latest."""

    if recipe_buffer_update_policy(buffer_data) == CubeUpdatePolicy.FOLLOW_LATEST:
        return None
    version = buffer_data.get("version")
    if not isinstance(version, str):
        return None
    stripped_version = version.strip()
    return stripped_version or None


def _format_use_target(cube_id: str, version: str | None) -> str:
    """Return a Sugar use target with an optional cube version pin."""

    target = _PATH_CODEC.encode_segment(cube_id)
    if version is None:
        return target
    return f"{target}@{_format_version_pin(version)}"


_DEFAULT_IO_PREFIXES = {"input", "output"}


def format_connect_endpoint(alias_sugar: str, key: JsonValue) -> str:
    """Format connect endpoints while normalizing standard input/output prefixes."""

    if key is None:
        return alias_sugar
    key_text = key if isinstance(key, str) else str(key)
    parts = key_text.split(".")
    if len(parts) >= 2 and parts[1] in _DEFAULT_IO_PREFIXES:
        parts = parts[1:]
    sanitized_parts = [_PATH_CODEC.encode_segment(part) for part in parts if part != ""]
    if not sanitized_parts:
        return alias_sugar
    return f"{alias_sugar}." + ".".join(sanitized_parts)


def _is_buffer_bypassed(buffer_data: Mapping[str, JsonValue]) -> bool:
    """Return whether one stripped recipe buffer is cube-bypassed."""

    return buffer_data.get("bypassed") is True


def _bypass_statement(statement: str, bypassed: bool) -> str:
    """Return a Sugar statement block, commenting each physical line when bypassed."""

    if not bypassed:
        return statement
    return "\n".join(
        f"# bypass {line}" if line else "# bypass" for line in statement.splitlines()
    )


def _seed_control_metadata_lines(
    *,
    ordered_aliases: list[str],
    field_control_states_by_alias: Mapping[
        str,
        Mapping[str, Mapping[str, SeedControlState]],
    ],
    label_resolver: SugarScriptLabelResolver | None,
) -> list[str]:
    """Return metadata comments for non-default cube seed control states."""

    lines: list[str] = []
    for alias in ordered_aliases:
        node_states = field_control_states_by_alias.get(alias)
        if not isinstance(node_states, Mapping):
            continue
        for node_name, field_states in sorted(node_states.items()):
            if not isinstance(field_states, Mapping):
                continue
            for field_key, state in sorted(field_states.items()):
                if not isinstance(state, SeedControlState):
                    continue
                if state.mode != SeedMode.FIXED:
                    continue
                script_node = (
                    label_resolver.node_label_for(alias, str(node_name))
                    if label_resolver is not None
                    else str(node_name)
                )
                script_field = (
                    label_resolver.input_label_for(
                        alias,
                        str(node_name),
                        str(field_key),
                    )
                    if label_resolver is not None
                    else str(field_key)
                )
                lines.append(
                    "# seed_control "
                    + json.dumps(
                        {
                            "alias": str(alias),
                            "field": script_field,
                            "mode": state.mode.value,
                            "node": script_node,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
    return lines


def _global_override_seed_control_metadata_lines(
    override_control_states: Mapping[str, SeedControlState],
    label_resolver: SugarScriptLabelResolver | None,
) -> list[str]:
    """Return metadata comments for non-default global override seed states."""

    lines: list[str] = []
    for override_key, state in sorted(override_control_states.items()):
        canonical_key = canonicalize_global_override_key(str(override_key))
        if canonical_key != "seed" or not isinstance(state, SeedControlState):
            continue
        if state.mode != SeedMode.FIXED:
            continue
        script_key = (
            label_resolver.global_input_label_for(canonical_key, ())
            if label_resolver is not None
            else canonical_key
        )
        lines.append(
            "# global_override_seed_control "
            + json.dumps(
                {
                    "key": script_key,
                    "mode": state.mode.value,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return lines


def _append_model_hash_comment(
    lines: list[str],
    *,
    field_identity: tuple[str, str, str],
    model_hashes_by_field: Mapping[tuple[str, str, str], str] | None,
) -> None:
    """Append a normalized SHA256 metadata comment for one set line when present."""

    if model_hashes_by_field is None:
        return
    sha256 = model_hashes_by_field.get(field_identity)
    if sha256 is None:
        return
    normalized_hash = sha256.strip().upper()
    if _SHA256_COMMENT_RE.fullmatch(f"# sha256 {normalized_hash}"):
        lines.append(f"# sha256 {normalized_hash}")


def _append_prompt_lora_hash_comments(
    lines: list[str],
    *,
    field_identity: tuple[str, str, str],
    prompt_lora_hashes_by_field: Mapping[tuple[str, str, str], Mapping[str, str]]
    | None,
) -> None:
    """Append normalized inline-LoRA SHA256 metadata comments for one field."""

    if prompt_lora_hashes_by_field is None:
        return
    lora_hashes = prompt_lora_hashes_by_field.get(field_identity)
    if not lora_hashes:
        return
    for prompt_name, sha256 in lora_hashes.items():
        stripped_name = prompt_name.strip()
        if not stripped_name:
            continue
        normalized_hash = sha256.strip().upper()
        if _SHA256_VALUE_RE.fullmatch(normalized_hash) is None:
            continue
        lines.append(
            _LORA_SHA256_COMMENT_PREFIX
            + json.dumps(
                {"name": stripped_name, "sha256": normalized_hash},
                sort_keys=True,
                separators=(",", ":"),
            )
        )


def _ordered_script_node_items(
    nodes: Mapping[object, object],
) -> list[tuple[object, object]]:
    """Return node entries with positive prompt nodes before negative prompt peers."""

    return _positive_prompt_before_negative_prompt(
        list(nodes.items()),
        lambda item: _prompt_polarity(
            item[0],
            item[1].get("label") if isinstance(item[1], Mapping) else None,
        ),
    )


def _ordered_script_input_items(
    inputs: Mapping[object, JsonValue],
) -> list[tuple[object, JsonValue]]:
    """Return input entries with positive prompt fields before negative prompt fields."""

    return _positive_prompt_before_negative_prompt(
        list(inputs.items()),
        lambda item: _prompt_polarity(item[0]),
    )


def _positive_prompt_before_negative_prompt(
    items: list[_T],
    polarity_for: Callable[[_T], str | None],
) -> list[_T]:
    """Move later positive prompt entries before earlier negative prompt entries."""

    first_negative_index: int | None = None
    positive_indexes_after_negative: list[int] = []
    for index, item in enumerate(items):
        polarity = polarity_for(item)
        if polarity == "negative" and first_negative_index is None:
            first_negative_index = index
            continue
        if (
            polarity == "positive"
            and first_negative_index is not None
            and index > first_negative_index
        ):
            positive_indexes_after_negative.append(index)
    if first_negative_index is None or not positive_indexes_after_negative:
        return items

    moved_indexes = frozenset(positive_indexes_after_negative)
    ordered_items: list[_T] = []
    inserted_positive_items = False
    for index, item in enumerate(items):
        if index == first_negative_index and not inserted_positive_items:
            ordered_items.extend(
                items[item_index] for item_index in positive_indexes_after_negative
            )
            inserted_positive_items = True
        if index not in moved_indexes:
            ordered_items.append(item)
    return ordered_items


def _prompt_polarity(*parts: object) -> str | None:
    """Return prompt polarity when text clearly names a positive/negative prompt."""

    text = " ".join(str(part).casefold() for part in parts if isinstance(part, str))
    if "prompt" not in text:
        return None
    has_positive = "positive" in text
    has_negative = "negative" in text
    if has_positive and not has_negative:
        return "positive"
    if has_negative and not has_positive:
        return "negative"
    return None


def _node_label_for_script(
    *,
    label_resolver: SugarScriptLabelResolver | None,
    alias: str,
    node_key: str,
) -> str:
    """Return the SugarScript node segment for one machine key."""

    if label_resolver is None:
        return node_key
    return label_resolver.node_label_for(alias, node_key)


def _input_label_for_script(
    *,
    label_resolver: SugarScriptLabelResolver | None,
    alias: str,
    node_key: str,
    input_key: str,
) -> str:
    """Return the SugarScript input segment for one machine key."""

    if label_resolver is None:
        return input_key
    return label_resolver.input_label_for(alias, node_key, input_key)


def _global_input_label_for_script(
    *,
    label_resolver: SugarScriptLabelResolver | None,
    input_key: str,
    participant_fields: Iterable[tuple[str, str, str]],
) -> str:
    """Return the SugarScript wildcard input segment for one machine key."""

    if label_resolver is None:
        return input_key
    return label_resolver.global_input_label_for(input_key, participant_fields)


def _endpoint_label_for_script(
    *,
    label_resolver: SugarScriptLabelResolver | None,
    alias: str,
    endpoint_key: JsonValue,
) -> JsonValue:
    """Return the SugarScript connect endpoint for one machine key."""

    if label_resolver is None:
        return endpoint_key
    return label_resolver.endpoint_label_for(alias, endpoint_key)


def _node_reference_for_script(
    label_resolver: SugarScriptLabelResolver | None,
    reference: str,
) -> str:
    """Return a node reference using labels when the resolver can map it."""

    parts = _PATH_CODEC.split(reference)
    if label_resolver is None or len(parts) != 2:
        return reference
    alias, node_key = parts
    return (
        f"{_PATH_CODEC.encode_segment(alias)}."
        f"{_PATH_CODEC.encode_segment(label_resolver.node_label_for(alias, node_key))}"
    )


def _field_reference_for_script(
    *,
    label_resolver: SugarScriptLabelResolver | None,
    alias: str,
    node_key: str,
    input_key: str,
) -> str:
    """Return a field reference using labels when the resolver can map it."""

    node_label = _node_label_for_script(
        label_resolver=label_resolver,
        alias=alias,
        node_key=node_key,
    )
    input_label = _input_label_for_script(
        label_resolver=label_resolver,
        alias=alias,
        node_key=node_key,
        input_key=input_key,
    )
    return (
        f"{_PATH_CODEC.encode_segment(alias)}."
        f"{_PATH_CODEC.encode_segment(node_label)}."
        f"{_PATH_CODEC.encode_segment(input_label)}"
    )


def _active_node_link(node: Mapping[str, JsonValue]) -> str | None:
    """Return a whole-node Sugar reference for active canonical node-link metadata."""

    link_cfg = node.get("node_link")
    if not isinstance(link_cfg, Mapping):
        return None
    from_cube = link_cfg.get("from_cube")
    from_node = link_cfg.get("from_node")
    return node_reference(
        str(from_cube) if isinstance(from_cube, str) else None,
        str(from_node) if isinstance(from_node, str) else None,
    )


def _legacy_prompt_node_link(
    node: Mapping[str, JsonValue],
    node_name: str,
) -> str | None:
    """Return a whole-node Sugar reference for legacy prompt-link metadata."""

    link_cfg = node.get("prompt_link")
    if not isinstance(link_cfg, Mapping):
        return None
    from_cube = link_cfg.get("from_cube")
    return node_reference(
        str(from_cube) if isinstance(from_cube, str) else None,
        node_name,
    )


def _disabled_node_names_for_alias(
    *,
    alias: str,
    disabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None,
) -> frozenset[str]:
    """Return policy-disabled node names for one alias."""

    if disabled_node_keys_by_alias is None:
        return frozenset()
    return frozenset(
        str(node_name) for node_name in disabled_node_keys_by_alias.get(alias, ())
    )


def _enabled_node_names_for_alias(
    *,
    alias: str,
    enabled_node_keys_by_alias: Mapping[str, Iterable[str]] | None,
) -> frozenset[str]:
    """Return policy-enabled node names for one alias."""

    if enabled_node_keys_by_alias is None:
        return frozenset()
    return frozenset(
        str(node_name) for node_name in enabled_node_keys_by_alias.get(alias, ())
    )


def _resolved_node_enabled(
    *,
    node_name: str,
    node: Mapping[str, object],
    enabled_node_names: frozenset[str],
    disabled_node_names: frozenset[str],
    activation_overrides_provided: bool,
) -> bool:
    """Return final executable activation for one node during serialization."""

    if activation_overrides_provided:
        if node_name in enabled_node_names:
            return True
        if node_name in disabled_node_names:
            return False
        return not _is_authored_bypass_node(node)
    explicit_enabled = node.get("enabled")
    if isinstance(explicit_enabled, bool):
        return explicit_enabled
    return not _is_authored_bypass_node(node)


def _node_activation_command(
    *,
    node: Mapping[str, object],
    node_enabled: bool,
) -> str | None:
    """Return the Sugar activation delta needed for one node."""

    authored_bypass = _is_authored_bypass_node(node)
    if authored_bypass and node_enabled:
        return "enable"
    if not authored_bypass and not node_enabled:
        return "disable"
    return None


def _is_authored_bypass_node(node: Mapping[str, object]) -> bool:
    """Return whether a node payload carries authored LiteGraph bypass mode."""

    mode = node.get("mode")
    return isinstance(mode, int) and not isinstance(mode, bool) and mode == 4


__all__ = [
    "SugarScriptLabelResolver",
    "SugarScriptSerializationError",
    "SugarScriptSerializationRequest",
    "SugarScriptSerializer",
]
