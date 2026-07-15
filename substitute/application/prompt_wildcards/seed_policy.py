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

"""Select deterministic prompt wildcard seeds from workflow cube controls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
    log_debug,
)

_LOGGER = get_logger("application.prompt_wildcards.seed_policy")


class PromptWildcardSeedCube(Protocol):
    """Describe cube state needed by wildcard seed selection."""

    buffer: Any


class PromptWildcardSeedWorkflow(Protocol):
    """Describe workflow state needed by wildcard seed selection."""

    stack_order: Sequence[str]
    cubes: Mapping[str, PromptWildcardSeedCube]


@dataclass(frozen=True, slots=True)
class PromptWildcardSeedSelection:
    """Capture one selected seed source for wildcard resolution."""

    seed: int | None
    cube_alias: str | None = None
    control_id: str | None = None


class PromptWildcardSeedPolicy:
    """Select wildcard seeds from prompt cube controls, then workflow controls."""

    def select_seed(
        self,
        *,
        workflow: PromptWildcardSeedWorkflow,
        prompt_cube_alias: str,
        workflow_id: str,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptWildcardSeedSelection:
        """Return the seed used to resolve one prompt field."""

        prompt_cube = workflow.cubes.get(prompt_cube_alias)
        if prompt_cube is not None:
            selection = self._first_seed_in_cube(prompt_cube_alias, prompt_cube)
            if selection.seed is not None:
                self._log_selection(
                    selection,
                    workflow_id=workflow_id,
                    prompt_cube_alias=prompt_cube_alias,
                    prompt_node_name=prompt_node_name,
                    prompt_field_key=prompt_field_key,
                )
                return selection

        for cube_alias in workflow.stack_order:
            cube = workflow.cubes.get(cube_alias)
            if cube is None:
                continue
            selection = self._first_seed_in_cube(cube_alias, cube)
            if selection.seed is not None:
                self._log_selection(
                    selection,
                    workflow_id=workflow_id,
                    prompt_cube_alias=prompt_cube_alias,
                    prompt_node_name=prompt_node_name,
                    prompt_field_key=prompt_field_key,
                )
                return selection

        log_info(
            _LOGGER,
            "No wildcard seed control found for prompt field.",
            workflow_id=workflow_id,
            cube_alias=prompt_cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        return PromptWildcardSeedSelection(seed=None)

    def _first_seed_in_cube(
        self,
        cube_alias: str,
        cube: PromptWildcardSeedCube,
    ) -> PromptWildcardSeedSelection:
        """Return the first seed control in authored surface order for one cube."""

        for control in _surface_controls(cube):
            if control.get("input_name") != "seed":
                continue
            control_id = control.get("control_id")
            symbol = control.get("symbol")
            input_name = control.get("input_name")
            if not isinstance(control_id, str):
                continue
            if not isinstance(symbol, str) or not isinstance(input_name, str):
                continue
            value = _node_input_value(cube.buffer, symbol, input_name)
            if isinstance(value, bool) or not isinstance(value, int):
                log_warning(
                    _LOGGER,
                    "Ignoring non-integer wildcard seed control value.",
                    cube_alias=cube_alias,
                    control_id=control_id,
                    value=value,
                )
                continue
            return PromptWildcardSeedSelection(
                seed=value,
                cube_alias=cube_alias,
                control_id=control_id,
            )
        return PromptWildcardSeedSelection(seed=None)

    @staticmethod
    def _log_selection(
        selection: PromptWildcardSeedSelection,
        *,
        workflow_id: str,
        prompt_cube_alias: str,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> None:
        """Log one selected wildcard seed source."""

        log_debug(
            _LOGGER,
            "Selected wildcard seed for prompt field.",
            workflow_id=workflow_id,
            cube_alias=prompt_cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            selected_seed_cube_alias=selection.cube_alias,
            selected_seed_control_id=selection.control_id,
            seed_value=selection.seed,
        )


def _surface_controls(cube: PromptWildcardSeedCube) -> tuple[Mapping[str, Any], ...]:
    """Return authored surface controls for one cube state."""

    original_cube = getattr(cube, "original_cube", {})
    surface = (
        original_cube.get("surface") if isinstance(original_cube, Mapping) else None
    )
    if not isinstance(surface, Mapping):
        surface = cube.buffer.get("surface")
    if not isinstance(surface, Mapping):
        return ()
    controls = surface.get("controls")
    if not isinstance(controls, list):
        return ()
    return tuple(control for control in controls if isinstance(control, Mapping))


def _node_input_value(
    buffer: Mapping[str, Any],
    node_name: str,
    input_name: str,
) -> object:
    """Return one node input value from a cube buffer."""

    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(node_name)
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(input_name)


__all__ = [
    "PromptWildcardSeedPolicy",
    "PromptWildcardSeedSelection",
]
