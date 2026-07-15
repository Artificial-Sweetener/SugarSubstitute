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

"""Parse persisted Sugar recipe scripts into deterministic domain state."""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from typing import Mapping, NamedTuple

from substitute.domain.common import (
    GlobalOverrideMap,
    GlobalOverrideSelectionMap,
    JsonObject,
    JsonValue,
)
from substitute.domain.cube_library import CubeUpdatePolicy
from substitute.domain.generation.seed_control import (
    SeedControlState,
    seed_mode_from_value,
)
from substitute.domain.recipes.sugar_ast import (
    ParsedSugarScript,
    SugarBufferMap,
)
from substitute.domain.recipes.sugar_literal_codec import SugarLiteralCodec
from substitute.domain.recipes.sugar_links import prompt_link_source_alias
from substitute.domain.recipes.sugar_path_codec import SugarPathCodec
from substitute.domain.workflow.override_keys import canonicalize_global_override_key
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("domain.recipes.sugar_script_parser")
_SHA256_COMMENT_RE = re.compile(r"^#\s*sha256\s+([A-Fa-f0-9]{64})\s*$")
_SHA256_VALUE_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
_LORA_SHA256_COMMENT_PREFIX = "# lora_sha256 "
_BYPASS_COMMENT_RE = re.compile(r"^#\s*bypass(?:\s+(.*))?$")
_LITERAL_CODEC = SugarLiteralCodec()
_PATH_CODEC = SugarPathCodec()


class _ScriptLine(NamedTuple):
    """Store one physical script line after bypass-comment normalization."""

    text: str
    bypassed: bool


def _script_lines_from_raw(lines: list[str]) -> list[_ScriptLine]:
    """Normalize raw script lines into active text plus cube-bypass provenance."""

    parsed_lines: list[_ScriptLine] = []
    for line in lines:
        stripped_line = line.strip()
        match = _BYPASS_COMMENT_RE.fullmatch(stripped_line)
        if match is None:
            parsed_lines.append(_ScriptLine(text=stripped_line, bypassed=False))
            continue
        parsed_lines.append(
            _ScriptLine(text=(match.group(1) or "").strip(), bypassed=True)
        )
    return parsed_lines


def _parse_node_revealed_comment(stripped_line: str) -> tuple[str, str] | None:
    """Parse one editor reveal-state metadata comment."""

    raw_json = stripped_line.removeprefix("# node_revealed ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    alias = payload.get("alias")
    node = payload.get("node")
    if not isinstance(alias, str) or not alias.strip():
        return None
    if not isinstance(node, str) or not node.strip():
        return None
    return alias.strip(), node.strip()


def _parse_node_enabled_comment(stripped_line: str) -> tuple[str, str, bool] | None:
    """Parse one editor activation-state metadata comment."""

    raw_json = stripped_line.removeprefix("# node_enabled ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    alias = payload.get("alias")
    node = payload.get("node")
    enabled = payload.get("enabled")
    if not isinstance(alias, str) or not alias.strip():
        return None
    if not isinstance(node, str) or not node.strip():
        return None
    if not isinstance(enabled, bool):
        return None
    return alias.strip(), node.strip(), enabled


def _parse_global_override_selection_comment(
    stripped_line: str,
) -> tuple[str, bool] | None:
    """Parse one global override menu-selection metadata comment."""

    raw_json = stripped_line.removeprefix("# global_override_selection ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    key = payload.get("key")
    selected = payload.get("selected")
    if not isinstance(key, str) or not key.strip():
        return None
    if not isinstance(selected, bool):
        return None
    return canonicalize_global_override_key(key.strip()), selected


def _parse_global_override_value_comment(
    stripped_line: str,
) -> tuple[str, JsonObject] | None:
    """Parse one partial-participation global override metadata comment."""

    raw_json = stripped_line.removeprefix("# global_override_value ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    key = payload.get("key")
    if not isinstance(key, str) or not key.strip():
        return None
    mode = payload.get("mode", "global")
    if not isinstance(mode, str) or not mode.strip():
        mode = "global"
    return canonicalize_global_override_key(key.strip()), {
        "value": payload.get("value"),
        "mode": mode,
    }


def _parse_seed_control_comment(
    stripped_line: str,
) -> tuple[str, str, str, SeedControlState] | None:
    """Parse one cube field seed-control metadata comment."""

    raw_json = stripped_line.removeprefix("# seed_control ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    alias = payload.get("alias")
    node = payload.get("node")
    field = payload.get("field")
    if not isinstance(alias, str) or not alias.strip():
        return None
    if not isinstance(node, str) or not node.strip():
        return None
    if not isinstance(field, str) or not field.strip():
        return None
    return (
        alias.strip(),
        node.strip(),
        field.strip(),
        SeedControlState(seed_mode_from_value(payload.get("mode"))),
    )


def _parse_global_override_seed_control_comment(
    stripped_line: str,
) -> tuple[str, SeedControlState] | None:
    """Parse one global override seed-control metadata comment."""

    raw_json = stripped_line.removeprefix("# global_override_seed_control ").strip()
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    key = payload.get("key")
    if not isinstance(key, str) or not key.strip():
        return None
    return (
        canonicalize_global_override_key(key.strip()),
        SeedControlState(seed_mode_from_value(payload.get("mode"))),
    )


def parse_sugar_script_document(sugar_script_str: str) -> ParsedSugarScript:
    """Parse Sugar DSL text into ordered buffers, global overrides, and project name."""

    lines = sugar_script_str.splitlines()
    script_lines = _script_lines_from_raw(lines)
    log_info(
        _LOGGER,
        "Parsing Sugar script document",
        line_count=len(lines),
        sugar_script_length=len(sugar_script_str),
        sugar_script_sha256=hashlib.sha256(
            sugar_script_str.encode("utf-8")
        ).hexdigest()[:16],
    )
    alias_to_cube: OrderedDict[str, str] = OrderedDict()
    alias_to_version: dict[str, str] = {}
    alias_to_update_policy: dict[str, str] = {}
    alias_to_bypassed: dict[str, bool] = {}
    use_re = re.compile(
        r'^use\s+(?:"([^"]+)"|([\w\-\\/. ]+))'
        r'(?:@(?:"([^"]*)"|([\w.]+)))?'
        r'\s+as\s+(?:"([^"]+)"|([\w\-\\/. ]+))$'
    )
    set_re = re.compile(r"^set\s+(.+?)\s*=\s*(.*)$")
    global_overrides: GlobalOverrideMap = {}
    global_override_selections: GlobalOverrideSelectionMap = {}
    field_control_states_by_alias: dict[
        str,
        dict[str, dict[str, SeedControlState]],
    ] = {}
    override_control_states: dict[str, SeedControlState] = {}
    model_hashes_by_field: OrderedDict[tuple[str, str, str], str] = OrderedDict()
    prompt_lora_hashes_by_field: OrderedDict[
        tuple[str, str, str],
        OrderedDict[str, str],
    ] = OrderedDict()
    project_name: str | None = None
    project_header_count = 0
    use_line_count = 0
    reveal_metadata_line_count = 0
    enabled_metadata_line_count = 0
    global_override_selection_line_count = 0
    parsed_global_override_selection_count = 0
    global_override_value_line_count = 0
    parsed_global_override_value_count = 0

    for script_line in script_lines:
        stripped_line = script_line.text
        if not script_line.bypassed and stripped_line.startswith("# Project:"):
            project_header_count += 1
            try:
                project_name = stripped_line.split(":", 1)[1].strip()
            except IndexError:
                pass
        matched_use = use_re.match(stripped_line)
        if matched_use:
            use_line_count += 1
            cube_id = (
                matched_use.group(1)
                if matched_use.group(1) is not None
                else matched_use.group(2)
            )
            alias = (
                matched_use.group(5)
                if matched_use.group(5) is not None
                else matched_use.group(6)
            )
            if cube_id is None or alias is None:
                continue
            stripped_alias = alias.strip()
            alias_to_cube[stripped_alias] = cube_id.strip()
            alias_to_bypassed[stripped_alias] = script_line.bypassed
            version_pin = (
                matched_use.group(3)
                if matched_use.group(3) is not None
                else matched_use.group(4)
            )
            if version_pin:
                alias_to_version[stripped_alias] = version_pin.strip()
                alias_to_update_policy[stripped_alias] = CubeUpdatePolicy.PINNED.value
            else:
                alias_to_update_policy[stripped_alias] = (
                    CubeUpdatePolicy.FOLLOW_LATEST.value
                )
            continue
        if script_line.bypassed:
            continue
        if stripped_line.startswith("# global_override_selection "):
            global_override_selection_line_count += 1
            selection = _parse_global_override_selection_comment(stripped_line)
            if selection is None:
                continue
            key, selected = selection
            global_override_selections[key] = selected
            parsed_global_override_selection_count += 1
            continue
        if stripped_line.startswith("# global_override_value "):
            global_override_value_line_count += 1
            override_value = _parse_global_override_value_comment(stripped_line)
            if override_value is None:
                continue
            key, override_payload = override_value
            global_overrides[key] = override_payload
            parsed_global_override_value_count += 1
            continue
        if stripped_line.startswith("# seed_control "):
            seed_control = _parse_seed_control_comment(stripped_line)
            if seed_control is None:
                continue
            alias, node, field, state = seed_control
            field_control_states_by_alias.setdefault(alias, {}).setdefault(
                node,
                {},
            )[field] = state
            continue
        if stripped_line.startswith("# global_override_seed_control "):
            override_seed_control = _parse_global_override_seed_control_comment(
                stripped_line
            )
            if override_seed_control is None:
                continue
            key, state = override_seed_control
            override_control_states[key] = state
            continue

    buffers: SugarBufferMap = OrderedDict(
        (
            alias,
            OrderedDict(
                cube_id=cube,
                **(
                    {"version": alias_to_version[alias]}
                    if alias in alias_to_version
                    else {}
                ),
                update_policy=alias_to_update_policy.get(
                    alias,
                    (
                        CubeUpdatePolicy.PINNED.value
                        if alias in alias_to_version
                        else CubeUpdatePolicy.FOLLOW_LATEST.value
                    ),
                ),
                bypassed=alias_to_bypassed.get(alias, False),
                nodes=OrderedDict(),
            ),
        )
        for alias, cube in alias_to_cube.items()
    )

    enable_re = re.compile(r'^enable\s+("[^"]+"|[\w]+)\.("[^"]+"|[\w]+)$')
    disable_re = re.compile(r'^disable\s+("[^"]+"|[\w]+)\.("[^"]+"|[\w]+)$')
    applied_reveal_metadata_count = 0
    for script_line in script_lines:
        stripped_line = script_line.text
        if not stripped_line.startswith("# node_revealed "):
            continue
        reveal_metadata_line_count += 1
        reveal_metadata = _parse_node_revealed_comment(stripped_line)
        if reveal_metadata is None:
            continue
        alias, node = reveal_metadata
        if alias not in buffers:
            continue
        buffer_nodes = buffers[alias].setdefault("nodes", OrderedDict())
        if not isinstance(buffer_nodes, OrderedDict):
            buffer_nodes = OrderedDict()
            buffers[alias]["nodes"] = buffer_nodes
        node_data = buffer_nodes.setdefault(node, {})
        if isinstance(node_data, dict):
            node_data["revealed"] = True
            applied_reveal_metadata_count += 1
    applied_enabled_metadata_count = 0
    for script_line in script_lines:
        stripped_line = script_line.text
        if not stripped_line.startswith("# node_enabled "):
            continue
        enabled_metadata_line_count += 1
        enabled_metadata = _parse_node_enabled_comment(stripped_line)
        if enabled_metadata is None:
            continue
        alias, node, enabled = enabled_metadata
        if alias not in buffers:
            continue
        buffer_nodes = buffers[alias].setdefault("nodes", OrderedDict())
        if not isinstance(buffer_nodes, OrderedDict):
            buffer_nodes = OrderedDict()
            buffers[alias]["nodes"] = buffer_nodes
        node_data = buffer_nodes.setdefault(node, {})
        if isinstance(node_data, dict):
            node_data["enabled"] = enabled
            applied_enabled_metadata_count += 1
    enable_line_count = 0
    applied_enable_count = 0
    for script_line in script_lines:
        matched_enable = enable_re.match(script_line.text)
        if not matched_enable:
            continue
        enable_line_count += 1
        alias = matched_enable.group(1).replace('"', "").strip()
        node = matched_enable.group(2).replace('"', "").strip()
        if alias not in buffers:
            continue
        buffer_nodes = buffers[alias].setdefault("nodes", OrderedDict())
        if not isinstance(buffer_nodes, OrderedDict):
            buffer_nodes = OrderedDict()
            buffers[alias]["nodes"] = buffer_nodes
        node_data = buffer_nodes.setdefault(node, {})
        if isinstance(node_data, dict):
            node_data["enabled"] = True
            applied_enable_count += 1
    disable_line_count = 0
    applied_disable_count = 0
    for script_line in script_lines:
        matched_disable = disable_re.match(script_line.text)
        if not matched_disable:
            continue
        disable_line_count += 1
        alias = matched_disable.group(1).replace('"', "").strip()
        node = matched_disable.group(2).replace('"', "").strip()
        if alias not in buffers:
            continue
        buffer_nodes = buffers[alias].setdefault("nodes", OrderedDict())
        if not isinstance(buffer_nodes, OrderedDict):
            buffer_nodes = OrderedDict()
            buffers[alias]["nodes"] = buffer_nodes
        node_data = buffer_nodes.setdefault(node, {})
        if isinstance(node_data, dict):
            node_data["enabled"] = False
            applied_disable_count += 1

    index = 0
    set_line_count = 0
    malformed_set_target_count = 0
    global_set_count = 0
    unknown_alias_set_count = 0
    node_link_set_count = 0
    input_set_count = 0
    while index < len(script_lines):
        script_line = script_lines[index]
        matched_set = set_re.match(script_line.text)
        if matched_set:
            set_line_count += 1
            target, value = matched_set.groups()
            target_parts = _PATH_CODEC.split(target)
            if len(target_parts) not in {2, 3}:
                malformed_set_target_count += 1
                index += 1
                continue
            alias = target_parts[0]
            node = target_parts[1]
            param = target_parts[2] if len(target_parts) == 3 else None
            value = value.strip()

            if alias == "*" and node == "*" and param is not None:
                global_overrides[canonicalize_global_override_key(param)] = {
                    "value": _LITERAL_CODEC.decode_scalar(value),
                    "mode": "global",
                }
                global_set_count += 1
                index += 1
                continue

            if alias not in buffers:
                unknown_alias_set_count += 1
                index += 1
                continue

            if param is None:
                parsed_ref = _PATH_CODEC.split(value)
                if len(parsed_ref) == 2:
                    node_collection = buffers[alias].setdefault("nodes", OrderedDict())
                    if not isinstance(node_collection, OrderedDict):
                        node_collection = OrderedDict()
                        buffers[alias]["nodes"] = node_collection
                    target_node = node_collection.setdefault(node, {"inputs": {}})
                    if isinstance(target_node, dict):
                        target_node["node_link"] = {
                            "from_cube": parsed_ref[0],
                            "from_node": parsed_ref[1],
                        }
                        node_link_set_count += 1
                index += 1
                continue

            is_triple_quoted = False
            if value.startswith('"""'):
                multiline_value_lines: list[str] = []
                first_line = value[3:]
                if first_line.endswith('"""'):
                    multiline_value_lines.append(first_line[:-3])
                else:
                    multiline_value_lines.append(first_line)
                    index += 1
                    while index < len(script_lines):
                        next_script_line = script_lines[index]
                        if next_script_line.bypassed != script_line.bypassed:
                            break
                        next_line = next_script_line.text
                        if next_line.endswith('"""'):
                            multiline_value_lines.append(next_line[:-3])
                            break
                        multiline_value_lines.append(next_line)
                        index += 1
                parsed_value: JsonValue = "\n".join(multiline_value_lines)
                is_triple_quoted = True
            else:
                parsed_value = _LITERAL_CODEC.decode_scalar(value)

            node_collection = buffers[alias].setdefault("nodes", OrderedDict())
            if not isinstance(node_collection, OrderedDict):
                node_collection = OrderedDict()
                buffers[alias]["nodes"] = node_collection
            if node not in node_collection:
                node_collection[node] = {"inputs": {}}

            target_node = node_collection[node]
            if not isinstance(target_node, dict):
                target_node = {"inputs": {}}
                node_collection[node] = target_node
            target_inputs = target_node.setdefault("inputs", {})
            if not isinstance(target_inputs, dict):
                target_inputs = {}
                target_node["inputs"] = target_inputs

            if not is_triple_quoted:
                ref_alias = prompt_link_source_alias(node, param, parsed_value)
                if ref_alias:
                    ref_parts = _PATH_CODEC.split(str(parsed_value))
                    ref_node = ref_parts[1] if len(ref_parts) == 3 else node
                    target_node["node_link"] = {
                        "from_cube": ref_alias,
                        "from_node": ref_node,
                    }
                    target_inputs[param] = ""
                elif (
                    param == "sampler_name"
                    and isinstance(parsed_value, str)
                    and "." in parsed_value
                    and parsed_value.count(".") == 2
                ):
                    from_cube, from_node, from_param = [
                        segment.replace('"', "").strip()
                        for segment in parsed_value.split(".", 2)
                    ]
                    if from_param == "sampler_name":
                        target_node["sampler_link"] = {
                            "from_cube": from_cube,
                            "from_node": from_node,
                        }
                        target_inputs.pop(param, None)
                    else:
                        target_inputs[param] = parsed_value
                elif (
                    param == "scheduler"
                    and isinstance(parsed_value, str)
                    and "." in parsed_value
                    and parsed_value.count(".") == 2
                ):
                    from_cube, from_node, from_param = [
                        segment.replace('"', "").strip()
                        for segment in parsed_value.split(".", 2)
                    ]
                    if from_param == "scheduler":
                        target_node["scheduler_link"] = {
                            "from_cube": from_cube,
                            "from_node": from_node,
                        }
                        target_inputs.pop(param, None)
                    else:
                        target_inputs[param] = parsed_value
                else:
                    target_inputs[param] = parsed_value
                    input_set_count += 1
            else:
                target_inputs[param] = parsed_value
                input_set_count += 1
            _record_adjacent_metadata_comments(
                lines=script_lines,
                set_line_index=index,
                field_identity=(alias, node, param),
                model_hashes_by_field=model_hashes_by_field,
                prompt_lora_hashes_by_field=prompt_lora_hashes_by_field,
            )
        index += 1

    log_info(
        _LOGGER,
        "Parsed Sugar script document",
        line_count=len(lines),
        project_name=project_name,
        project_header_count=project_header_count,
        use_line_count=use_line_count,
        alias_count=len(buffers),
        aliases=list(buffers.keys()),
        cube_ids=[str(buffer.get("cube_id", "")) for buffer in buffers.values()],
        reveal_metadata_line_count=reveal_metadata_line_count,
        applied_reveal_metadata_count=applied_reveal_metadata_count,
        enabled_metadata_line_count=enabled_metadata_line_count,
        applied_enabled_metadata_count=applied_enabled_metadata_count,
        enable_line_count=enable_line_count,
        applied_enable_count=applied_enable_count,
        disable_line_count=disable_line_count,
        applied_disable_count=applied_disable_count,
        set_line_count=set_line_count,
        malformed_set_target_count=malformed_set_target_count,
        global_set_count=global_set_count,
        unknown_alias_set_count=unknown_alias_set_count,
        node_link_set_count=node_link_set_count,
        input_set_count=input_set_count,
        global_override_count=len(global_overrides),
        global_override_selection_line_count=global_override_selection_line_count,
        parsed_global_override_selection_count=(parsed_global_override_selection_count),
        global_override_value_line_count=global_override_value_line_count,
        parsed_global_override_value_count=parsed_global_override_value_count,
        model_hash_count=len(model_hashes_by_field),
        prompt_lora_hash_field_count=len(prompt_lora_hashes_by_field),
        prompt_lora_hash_count=sum(
            len(lora_hashes) for lora_hashes in prompt_lora_hashes_by_field.values()
        ),
    )
    return ParsedSugarScript(
        buffers=buffers,
        global_overrides=global_overrides,
        global_override_selections=global_override_selections,
        field_control_states_by_alias=field_control_states_by_alias,
        override_control_states=override_control_states,
        model_hashes_by_field=model_hashes_by_field,
        prompt_lora_hashes_by_field=prompt_lora_hashes_by_field,
        project_name=project_name,
    )


def _record_adjacent_metadata_comments(
    *,
    lines: list[_ScriptLine],
    set_line_index: int,
    field_identity: tuple[str, str, str],
    model_hashes_by_field: OrderedDict[tuple[str, str, str], str],
    prompt_lora_hashes_by_field: OrderedDict[
        tuple[str, str, str],
        OrderedDict[str, str],
    ],
) -> None:
    """Record recognized metadata comments immediately below one input set line."""

    comment_index = set_line_index + 1
    set_line = lines[set_line_index]
    while comment_index < len(lines):
        script_line = lines[comment_index]
        if script_line.bypassed != set_line.bypassed:
            return
        stripped_line = script_line.text
        if not _is_adjacent_metadata_comment(stripped_line):
            return
        match = _SHA256_COMMENT_RE.fullmatch(stripped_line)
        if match is not None:
            model_hashes_by_field[field_identity] = match.group(1).upper()
            comment_index += 1
            continue
        parsed_lora_hash = _parse_prompt_lora_sha256_comment(stripped_line)
        if parsed_lora_hash is not None:
            prompt_name, sha256 = parsed_lora_hash
            lora_hashes = prompt_lora_hashes_by_field.setdefault(
                field_identity,
                OrderedDict(),
            )
            lora_hashes[prompt_name] = sha256
        comment_index += 1


def _is_adjacent_metadata_comment(stripped_line: str) -> bool:
    """Return whether a stripped line is an adjacent recipe metadata comment."""

    return stripped_line.startswith("# sha256 ") or stripped_line.startswith(
        _LORA_SHA256_COMMENT_PREFIX
    )


def _parse_prompt_lora_sha256_comment(line: str) -> tuple[str, str] | None:
    """Return inline-LoRA prompt name and SHA256 from a strict JSON comment."""

    if not line.startswith(_LORA_SHA256_COMMENT_PREFIX):
        return None
    payload_text = line[len(_LORA_SHA256_COMMENT_PREFIX) :]
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    name = payload.get("name")
    sha256 = payload.get("sha256")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(sha256, str):
        return None
    normalized_hash = sha256.strip().upper()
    if _SHA256_VALUE_RE.fullmatch(normalized_hash) is None:
        return None
    return name.strip(), normalized_hash


__all__ = [
    "parse_sugar_script_document",
]
