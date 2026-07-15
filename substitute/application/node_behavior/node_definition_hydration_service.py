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

"""Hydrate live node definitions required by editor projection."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from time import perf_counter
from typing import Protocol, cast

from substitute.application.ports import (
    NodeDefinitionHydrationResult,
)
from substitute.shared.logging.logger import get_logger, log_timing, log_warning

from .live_definition_authority import (
    LiveNodeDefinitionError,
    MissingLiveNodeDefinition,
)
from .node_definition_requirements import (
    NodeDefinitionRequirement,
    required_node_definition_requirements_for_editor_projection,
)

_LOGGER = get_logger("application.node_behavior.node_definition_hydration_service")


class CubeStateProtocol(Protocol):
    """Describe the cube-state buffer access required for hydration."""

    buffer: dict[str, object]


class EditorNodeDefinitionHydrationService:
    """Hydrate live node definitions required for editor projection."""

    def __init__(self, hydrator: object | None) -> None:
        """Store the optional foreground hydrator."""

        self._hydrator = hydrator

    def hydrate_for_projection(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: Sequence[str],
    ) -> NodeDefinitionHydrationResult | None:
        """Hydrate node definitions for loaded cubes in stack order."""

        hydration_started_at = perf_counter()
        buffers = _buffers_in_stack_order(
            cube_states=cube_states, stack_order=stack_order
        )
        requirements = required_node_definition_requirements_for_editor_projection(
            buffers
        )
        node_classes = tuple(
            sorted({requirement.class_type for requirement in requirements})
        )
        ensure_node_definitions = _ensure_node_definitions_callable(self._hydrator)
        if ensure_node_definitions is None:
            log_warning(
                _LOGGER,
                "Skipped editor node definition hydration without foreground hydrator",
                stack_order_count=len(stack_order),
                requested_node_classes=",".join(node_classes),
            )
            if node_classes:
                raise LiveNodeDefinitionError(
                    operation="hydrate editor projection node definitions",
                    missing_definitions=_missing_definitions_for_classes(
                        node_classes,
                        requirements=requirements,
                    ),
                )
            return None
        result = ensure_node_definitions(node_classes)
        log_timing(
            _LOGGER,
            "Hydrated editor projection node definitions",
            started_at=hydration_started_at,
            stack_order_count=len(stack_order),
            requested_count=len(result.requested),
            available_count=len(result.available),
            unavailable_count=len(result.unavailable),
            unavailable_node_classes=",".join(result.unavailable),
        )
        if result.unavailable:
            log_warning(
                _LOGGER,
                "Editor projection node definition hydration left unavailable classes",
                stack_order_count=len(stack_order),
                unavailable_node_classes=",".join(result.unavailable),
            )
            raise LiveNodeDefinitionError(
                operation="hydrate editor projection node definitions",
                missing_definitions=_missing_definitions_for_classes(
                    result.unavailable,
                    requirements=requirements,
                ),
            )
        return result


def _ensure_node_definitions_callable(
    hydrator: object | None,
) -> Callable[[Sequence[str]], NodeDefinitionHydrationResult] | None:
    """Return the foreground hydration method when the object provides one."""

    ensure_node_definitions = getattr(hydrator, "ensure_node_definitions", None)
    if not callable(ensure_node_definitions):
        return None
    return cast(
        Callable[[Sequence[str]], NodeDefinitionHydrationResult],
        ensure_node_definitions,
    )


def _missing_definitions_for_classes(
    node_classes: Sequence[str],
    *,
    requirements: Sequence[NodeDefinitionRequirement] = (),
) -> tuple[MissingLiveNodeDefinition, ...]:
    """Return missing-definition records for unavailable class names."""

    unavailable_classes = {
        node_class for node_class in node_classes if node_class.strip()
    }
    by_class_and_alias: dict[tuple[str, str], set[str]] = {}
    for requirement in requirements:
        if requirement.class_type not in unavailable_classes:
            continue
        by_class_and_alias.setdefault(
            (requirement.class_type, requirement.cube_alias),
            set(),
        ).add(requirement.node_name)
    attributed = tuple(
        MissingLiveNodeDefinition(
            class_type=class_type,
            cube_aliases=(cube_alias,),
            node_names=tuple(sorted(node_names)),
        )
        for (class_type, cube_alias), node_names in sorted(by_class_and_alias.items())
    )
    attributed_classes = {item.class_type for item in attributed}
    unattributed = tuple(
        MissingLiveNodeDefinition(class_type=node_class)
        for node_class in sorted(unavailable_classes - attributed_classes)
    )
    return (*attributed, *unattributed)


def _buffers_in_stack_order(
    *,
    cube_states: Mapping[str, object],
    stack_order: Sequence[str],
) -> dict[str, Mapping[str, object]]:
    """Return cube buffers ordered by active stack aliases."""

    buffers: dict[str, Mapping[str, object]] = {}
    for alias in stack_order:
        cube_state = cube_states.get(alias)
        buffer = getattr(cube_state, "buffer", None)
        if isinstance(buffer, Mapping):
            buffers[alias] = buffer
    return buffers


__all__ = ["EditorNodeDefinitionHydrationService"]
