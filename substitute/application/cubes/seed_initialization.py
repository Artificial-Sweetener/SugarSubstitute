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

"""Initialize unset cube seed controls during runtime materialization."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import cast

from substitute.domain.common import JsonObject
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.cubes.seed_initialization")
DEFAULT_RANDOM_SEED_MAX = 18_446_744_073_709_551_615
_MISSING = object()


@dataclass(frozen=True)
class SeedInitializationResult:
    """Describe seed controls initialized during cube runtime materialization."""

    initialized_count: int
    skipped_explicit_patch_count: int
    skipped_invalid_range_count: int = 0


def initialize_fresh_seed_controls(
    cube_buffer: JsonObject,
    *,
    buffer_patch: object | None,
    randint: Callable[[int, int], int],
    cube_id: str = "",
    cube_alias: str = "",
    cube_load_trace_id: str = "",
) -> SeedInitializationResult:
    """Initialize unset surface-backed seed controls in one mutable cube buffer."""

    nodes = cube_buffer.get("nodes")
    surface = cube_buffer.get("surface")
    if not isinstance(nodes, MutableMapping) or not isinstance(surface, Mapping):
        return SeedInitializationResult(
            initialized_count=0,
            skipped_explicit_patch_count=0,
        )

    controls = surface.get("controls")
    if not isinstance(controls, list):
        return SeedInitializationResult(
            initialized_count=0,
            skipped_explicit_patch_count=0,
        )

    initialized_count = 0
    skipped_explicit_patch_count = 0
    skipped_invalid_range_count = 0
    for control in controls:
        if not isinstance(control, Mapping) or control.get("input_name") != "seed":
            continue
        symbol = control.get("symbol")
        class_type = control.get("class_type")
        if not isinstance(symbol, str) or not isinstance(class_type, str):
            continue
        node = nodes.get(symbol)
        if not isinstance(node, MutableMapping):
            continue
        inputs = _mutable_inputs(node)
        if inputs is None:
            continue
        patched_seed = _buffer_patch_seed_value(buffer_patch, symbol=symbol)
        if patched_seed is not _MISSING:
            inputs["seed"] = patched_seed
            skipped_explicit_patch_count += 1
            continue
        current_value = inputs.get("seed", _MISSING)
        if not _is_unset_seed_value(current_value):
            continue
        bounds = _seed_bounds(cube_buffer, class_type=class_type)
        if bounds is None:
            skipped_invalid_range_count += 1
            log_warning(
                _LOGGER,
                "Skipped cube seed initialization for invalid seed range",
                cube_id=cube_id,
                cube_alias=cube_alias,
                cube_load_trace_id=cube_load_trace_id,
                node_name=symbol,
                field_key="seed",
            )
            continue
        minimum, maximum = bounds
        inputs["seed"] = randint(minimum, maximum)
        initialized_count += 1

    return SeedInitializationResult(
        initialized_count=initialized_count,
        skipped_explicit_patch_count=skipped_explicit_patch_count,
        skipped_invalid_range_count=skipped_invalid_range_count,
    )


def _mutable_inputs(
    node: MutableMapping[object, object],
) -> MutableMapping[str, object] | None:
    """Return mutable node inputs, creating them when absent."""

    inputs = node.get("inputs")
    if inputs is None:
        inputs = {}
        node["inputs"] = inputs
    if not isinstance(inputs, MutableMapping):
        return None
    return cast(MutableMapping[str, object], inputs)


def _buffer_patch_seed_value(buffer_patch: object | None, *, symbol: str) -> object:
    """Return one explicit persisted seed patch value, or the missing sentinel."""

    if not isinstance(buffer_patch, Mapping):
        return _MISSING
    nodes = buffer_patch.get("nodes")
    if not isinstance(nodes, Mapping):
        return _MISSING
    node_patch = nodes.get(symbol)
    if not isinstance(node_patch, Mapping):
        return _MISSING
    inputs_patch = node_patch.get("inputs")
    if not isinstance(inputs_patch, Mapping) or "seed" not in inputs_patch:
        return _MISSING
    return inputs_patch["seed"]


def _is_unset_seed_value(value: object) -> bool:
    """Return whether one seed value should be treated as unset on fresh load."""

    if value is _MISSING or value is None:
        return True
    if isinstance(value, str):
        return value.strip() in {"", "0"}
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == 0
    if isinstance(value, float):
        return value == 0.0
    return False


def _seed_bounds(
    cube_buffer: JsonObject,
    *,
    class_type: str,
) -> tuple[int, int] | None:
    """Return nonzero seed generation bounds for one node class."""

    definition = _definition_for_class(cube_buffer, class_type=class_type)
    constraints = _seed_constraints(definition)
    minimum = _coerce_int(constraints.get("min") if constraints else None, default=0)
    maximum = _coerce_int(
        constraints.get("max") if constraints else None,
        default=DEFAULT_RANDOM_SEED_MAX,
    )
    lower = max(1, minimum)
    if maximum < lower:
        return None
    return lower, maximum


def _definition_for_class(
    cube_buffer: JsonObject,
    *,
    class_type: str,
) -> Mapping[str, object] | None:
    """Return a node-definition mapping for one class type when available."""

    definitions = cube_buffer.get("definitions")
    if not isinstance(definitions, Mapping):
        return None
    definition = definitions.get(class_type)
    return definition if isinstance(definition, Mapping) else None


def _seed_constraints(
    definition: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    """Return the seed constraint mapping from required or optional inputs."""

    if definition is None:
        return None
    input_payload = definition.get("input")
    if not isinstance(input_payload, Mapping):
        return None
    for section_name in ("required", "optional"):
        section = input_payload.get(section_name)
        if not isinstance(section, Mapping):
            continue
        field_spec = section.get("seed")
        constraints = _constraints_from_field_spec(field_spec)
        if constraints is not None:
            return constraints
    return None


def _constraints_from_field_spec(field_spec: object) -> Mapping[str, object] | None:
    """Return constraints from a Comfy field definition tuple/list."""

    if not isinstance(field_spec, list | tuple) or len(field_spec) < 2:
        return None
    constraints = field_spec[1]
    return constraints if isinstance(constraints, Mapping) else None


def _coerce_int(value: object, *, default: int) -> int:
    """Coerce numeric seed bounds while preserving a safe fallback."""

    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default
