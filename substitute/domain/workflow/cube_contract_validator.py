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

"""Validate Sugar cube contract invariants at the Substitute load boundary."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from substitute.domain.cubes import (
    is_subgraph_wrapper_class_type,
)


class CubeContractError(RuntimeError):
    """Raised when a cube document violates the runtime contract."""


def validate_cube_contract(cube_document: Mapping[str, Any], *, cube_name: str) -> None:
    """Validate wrapper/subgraph contract invariants.

    Args:
        cube_document: Loaded cube JSON payload.
        cube_name: User-facing cube name for diagnostics.

    Raises:
        CubeContractError: If the cube violates required contract rules.
    """

    if not isinstance(cube_document, Mapping):
        raise CubeContractError(f"Cube '{cube_name}' must be a JSON object.")

    nodes = cube_document.get("nodes")
    if not isinstance(nodes, Mapping):
        raise CubeContractError(f"Cube '{cube_name}' must include a nodes mapping.")

    wrapper_classes = _collect_top_level_wrapper_classes(nodes)
    subgraphs = cube_document.get("subgraphs")
    subgraph_index = _index_subgraphs(subgraphs)

    if wrapper_classes:
        if not subgraph_index:
            raise CubeContractError(
                f"Cube '{cube_name}' has UUID wrapper nodes but no subgraph definitions."
            )

        missing = sorted(wrapper_classes - set(subgraph_index.keys()))
        if missing:
            missing_text = ", ".join(missing)
            raise CubeContractError(
                f"Cube '{cube_name}' is missing subgraph definition(s) for wrapper class_type(s): {missing_text}."
            )

        _validate_reachable_subgraphs(
            cube_name=cube_name,
            root_wrapper_classes=wrapper_classes,
            subgraph_index=subgraph_index,
        )


def _collect_top_level_wrapper_classes(nodes: Mapping[str, Any]) -> set[str]:
    """Collect UUID wrapper class types from cube nodes."""

    wrappers: set[str] = set()
    for node in nodes.values():
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        normalized = class_type.strip()
        if is_subgraph_wrapper_class_type(normalized):
            wrappers.add(normalized)
    return wrappers


def _index_subgraphs(subgraphs: Any) -> dict[str, Mapping[str, Any]]:
    """Index subgraph payload entries by id."""

    if not isinstance(subgraphs, Sequence) or isinstance(subgraphs, (str, bytes)):
        return {}
    index: dict[str, Mapping[str, Any]] = {}
    for entry in subgraphs:
        if not isinstance(entry, Mapping):
            continue
        sub_id = entry.get("id")
        if not isinstance(sub_id, str):
            continue
        normalized = sub_id.strip()
        if normalized:
            index[normalized] = entry
    return index


def _validate_reachable_subgraphs(
    *,
    cube_name: str,
    root_wrapper_classes: set[str],
    subgraph_index: Mapping[str, Mapping[str, Any]],
) -> None:
    """Validate all subgraphs reachable from surface wrapper nodes."""

    visited: set[str] = set()
    visiting: list[str] = []

    def visit(wrapper_type: str, *, parent_type: str | None = None) -> None:
        """Depth-first validate one wrapper and its nested wrapper dependencies."""

        if wrapper_type in visiting:
            cycle_start = visiting.index(wrapper_type)
            cycle_path = [*visiting[cycle_start:], wrapper_type]
            raise CubeContractError(
                f"Cube '{cube_name}' has cyclic subgraph wrapper references: {' -> '.join(cycle_path)}."
            )
        if wrapper_type in visited:
            return

        subgraph = subgraph_index.get(wrapper_type)
        if subgraph is None:
            if parent_type is None:
                raise CubeContractError(
                    f"Cube '{cube_name}' is missing subgraph definition for wrapper class_type '{wrapper_type}'."
                )
            raise CubeContractError(
                f"Cube '{cube_name}' subgraph '{parent_type}' references missing nested subgraph definition '{wrapper_type}'."
            )

        _validate_subgraph_contract(
            cube_name=cube_name,
            wrapper_type=wrapper_type,
            subgraph=subgraph,
        )

        visiting.append(wrapper_type)
        for nested_wrapper_type in sorted(
            _collect_subgraph_wrapper_references(subgraph)
        ):
            visit(nested_wrapper_type, parent_type=wrapper_type)
        visiting.pop()
        visited.add(wrapper_type)

    for root_wrapper_type in sorted(root_wrapper_classes):
        visit(root_wrapper_type)


def _validate_subgraph_contract(
    *,
    cube_name: str,
    wrapper_type: str,
    subgraph: Mapping[str, Any],
) -> None:
    """Validate the local interface and body contract for one subgraph wrapper."""

    if not isinstance(subgraph.get("inputs"), list):
        raise CubeContractError(
            f"Cube '{cube_name}' subgraph '{wrapper_type}' must include an inputs array."
        )
    if not isinstance(subgraph.get("outputs"), list):
        raise CubeContractError(
            f"Cube '{cube_name}' subgraph '{wrapper_type}' must include an outputs array."
        )
    if not _subgraph_has_executable_body(subgraph):
        raise CubeContractError(
            f"Cube '{cube_name}' subgraph '{wrapper_type}' must include executable nodes."
        )
    _validate_subgraph_interface_labels(
        cube_name=cube_name,
        wrapper_type=wrapper_type,
        entries=subgraph.get("inputs"),
        field_name="inputs",
    )
    _validate_subgraph_interface_labels(
        cube_name=cube_name,
        wrapper_type=wrapper_type,
        entries=subgraph.get("outputs"),
        field_name="outputs",
    )
    _validate_wrapper_interface_link_coverage(
        cube_name=cube_name,
        wrapper_type=wrapper_type,
        subgraph=subgraph,
    )


def _validate_subgraph_interface_labels(
    *,
    cube_name: str,
    wrapper_type: str,
    entries: Any,
    field_name: str,
) -> None:
    """Validate required public subgraph interface names and labels."""

    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return
    labels: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        name = _required_interface_text(
            entry.get("name"),
            cube_name=cube_name,
            wrapper_type=wrapper_type,
            field_name=field_name,
            index=index,
            key="name",
        )
        label = _required_interface_text(
            entry.get("label"),
            cube_name=cube_name,
            wrapper_type=wrapper_type,
            field_name=field_name,
            index=index,
            key="label",
        )
        previous_name = labels.get(label)
        if previous_name is not None:
            raise CubeContractError(
                f"Cube '{cube_name}' subgraph '{wrapper_type}' has duplicate "
                f"{field_name} label '{label}' for machine names "
                f"'{previous_name}' and '{name}'."
            )
        labels[label] = name


def _required_interface_text(
    value: object,
    *,
    cube_name: str,
    wrapper_type: str,
    field_name: str,
    index: int,
    key: str,
) -> str:
    """Return required interface text or fail with cube context."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    raise CubeContractError(
        f"Cube '{cube_name}' subgraph '{wrapper_type}' {field_name}[{index}] "
        f"must include a non-empty '{key}'."
    )


def _collect_subgraph_wrapper_references(subgraph: Mapping[str, Any]) -> set[str]:
    """Collect UUID wrappers referenced by one subgraph body."""

    nodes = subgraph.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        return set()
    wrappers: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("type")
        if not isinstance(class_type, str):
            class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        normalized = class_type.strip()
        if is_subgraph_wrapper_class_type(normalized):
            wrappers.add(normalized)
    return wrappers


def _subgraph_has_executable_body(subgraph: Mapping[str, Any]) -> bool:
    """Return whether a subgraph contains at least one executable node."""

    nodes = subgraph.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        return False
    if not nodes:
        return False
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        class_type = node.get("type")
        if not isinstance(class_type, str):
            class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type.strip():
            return True
    return False


def _validate_wrapper_interface_link_coverage(
    *,
    cube_name: str,
    wrapper_type: str,
    subgraph: Mapping[str, Any],
) -> None:
    """Validate that interface links are declared in subgraph inputs/outputs metadata."""

    required_input_link_ids, required_output_link_ids = _collect_interface_link_ids(
        subgraph
    )
    declared_input_link_ids = _collect_declared_interface_link_ids(
        subgraph.get("inputs"),
        field_name="inputs",
        cube_name=cube_name,
        wrapper_type=wrapper_type,
    )
    declared_output_link_ids = _collect_declared_interface_link_ids(
        subgraph.get("outputs"),
        field_name="outputs",
        cube_name=cube_name,
        wrapper_type=wrapper_type,
    )

    missing_input_link_ids = sorted(required_input_link_ids - declared_input_link_ids)
    if missing_input_link_ids:
        missing_text = ", ".join(str(link_id) for link_id in missing_input_link_ids)
        raise CubeContractError(
            f"Cube '{cube_name}' subgraph '{wrapper_type}' is missing inputs.linkIds mappings for interface link id(s): {missing_text}."
        )

    missing_output_link_ids = sorted(
        required_output_link_ids - declared_output_link_ids
    )
    if missing_output_link_ids:
        missing_text = ", ".join(str(link_id) for link_id in missing_output_link_ids)
        raise CubeContractError(
            f"Cube '{cube_name}' subgraph '{wrapper_type}' is missing outputs.linkIds mappings for interface link id(s): {missing_text}."
        )


def _collect_interface_link_ids(
    subgraph: Mapping[str, Any],
) -> tuple[set[int], set[int]]:
    """Collect interface link ids for input and output bridge nodes."""

    input_interface_ids = _collect_interface_ids(
        subgraph.get("inputNode"), default="-10"
    )
    output_interface_ids = _collect_interface_ids(
        subgraph.get("outputNode"),
        default="-20",
    )
    required_input_link_ids: set[int] = set()
    required_output_link_ids: set[int] = set()

    links = subgraph.get("links")
    if not isinstance(links, Sequence) or isinstance(links, (str, bytes)):
        return required_input_link_ids, required_output_link_ids

    for raw_link in links:
        normalized = _normalize_link(raw_link)
        if normalized is None:
            continue
        if normalized["origin_id"] in input_interface_ids:
            required_input_link_ids.add(normalized["id"])
        if normalized["target_id"] in output_interface_ids:
            required_output_link_ids.add(normalized["id"])

    return required_input_link_ids, required_output_link_ids


def _collect_declared_interface_link_ids(
    interface_entries: Any,
    *,
    field_name: str,
    cube_name: str,
    wrapper_type: str,
) -> set[int]:
    """Collect all declared link ids from `inputs` or `outputs` interface metadata."""

    if not isinstance(interface_entries, Sequence) or isinstance(
        interface_entries, (str, bytes)
    ):
        return set()

    declared: set[int] = set()
    for index, entry in enumerate(interface_entries):
        if not isinstance(entry, Mapping):
            raise CubeContractError(
                f"Cube '{cube_name}' subgraph '{wrapper_type}' has non-object entry in '{field_name}' at index {index}."
            )
        link_ids = entry.get("linkIds")
        if link_ids is None:
            continue
        if not isinstance(link_ids, Sequence) or isinstance(link_ids, (str, bytes)):
            raise CubeContractError(
                f"Cube '{cube_name}' subgraph '{wrapper_type}' has non-list linkIds in '{field_name}' at index {index}."
            )
        for raw_link_id in link_ids:
            parsed_link_id = _coerce_int(raw_link_id)
            if parsed_link_id is None:
                continue
            declared.add(parsed_link_id)
    return declared


def _collect_interface_ids(value: Any, *, default: str) -> set[str]:
    """Collect declared interface node ids, falling back to standard LiteGraph ids."""

    ids: set[str] = set()
    if isinstance(value, Mapping):
        node_id = _normalize_node_id(value.get("id"))
        if node_id is not None:
            ids.add(node_id)
    if not ids:
        ids.add(default)
    return ids


def _normalize_link(raw: Any) -> dict[str, Any] | None:
    """Normalize a legacy or object-style link entry into a unified shape."""

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        values = list(raw)
        if len(values) < 5:
            return None
        link_id = _coerce_int(values[0])
        origin_id = _normalize_node_id(values[1])
        origin_slot = _coerce_int(values[2], default=0)
        target_id = _normalize_node_id(values[3])
        target_port = values[4]
        if link_id is None or origin_id is None or target_id is None:
            return None
        return {
            "id": link_id,
            "origin_id": origin_id,
            "origin_slot": origin_slot,
            "target_id": target_id,
            "target_port": target_port,
        }
    if isinstance(raw, Mapping):
        link_id = _coerce_int(raw.get("id"))
        origin_id = _normalize_node_id(raw.get("origin_id") or raw.get("originId"))
        origin_slot = _coerce_int(
            raw.get("origin_slot") or raw.get("originSlot"), default=0
        )
        target_id = _normalize_node_id(raw.get("target_id") or raw.get("targetId"))
        target_port = (
            raw.get("target_port") or raw.get("targetPort") or raw.get("target_slot")
        )
        if link_id is None or origin_id is None or target_id is None:
            return None
        return {
            "id": link_id,
            "origin_id": origin_id,
            "origin_slot": origin_slot,
            "target_id": target_id,
            "target_port": target_port,
        }
    return None


def _normalize_node_id(value: Any) -> str | None:
    """Convert serialized node ids to deterministic string form."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return str(value)


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    """Parse integer-like values and preserve explicit defaults on failure."""

    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(stripped)
        except ValueError:
            try:
                return int(float(stripped))
            except ValueError:
                return default
    try:
        return int(value)
    except Exception:
        return default


__all__ = [
    "CubeContractError",
    "validate_cube_contract",
]
