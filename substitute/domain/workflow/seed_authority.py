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

"""Own effective workflow seed selection and source precedence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypeGuard

from substitute.domain.workflow.override_keys import canonicalize_global_override_key

SEED_OVERRIDE_KEY = "seed"


class WorkflowSeedCube(Protocol):
    """Describe cube state required to locate authored seed controls."""

    @property
    def buffer(self) -> Mapping[str, Any]:
        """Return mutable runtime cube content through a read-only view."""

    @property
    def original_cube(self) -> Mapping[str, Any]:
        """Return authored cube content through a read-only view."""


class WorkflowSeedState(Protocol):
    """Describe workflow state required to determine its effective seed."""

    @property
    def global_overrides(self) -> Mapping[str, object]:
        """Return workflow global overrides through a read-only view."""

    @property
    def stack_order(self) -> Sequence[str]:
        """Return authored workflow cube order."""

    @property
    def cubes(self) -> Mapping[str, WorkflowSeedCube]:
        """Return workflow cubes keyed by alias through a read-only view."""


class WorkflowSeedSource(StrEnum):
    """Identify the authoritative source of an effective workflow seed."""

    GLOBAL_OVERRIDE = "global_override"
    CUBE_CONTROL = "cube_control"


@dataclass(frozen=True, slots=True)
class WorkflowSeedSelection:
    """Capture an effective seed together with its workflow provenance."""

    seed: int | None
    source: WorkflowSeedSource | None = None
    override_key: str | None = None
    cube_alias: str | None = None
    control_id: str | None = None


class WorkflowSeedSelector(Protocol):
    """Select the effective seed from workflow state."""

    def select(self, workflow: WorkflowSeedState) -> WorkflowSeedSelection:
        """Return the effective workflow seed and its provenance."""


class WorkflowSeedAuthority:
    """Select the global seed, then the first seed in workflow stack order."""

    def select(self, workflow: WorkflowSeedState) -> WorkflowSeedSelection:
        """Return the effective seed and the workflow element that owns it."""

        override_key = self.active_global_override_key(workflow)
        if override_key is not None:
            override = workflow.global_overrides[override_key]
            if isinstance(override, Mapping):
                value = override.get("value")
                if _is_seed(value):
                    return WorkflowSeedSelection(
                        seed=value,
                        source=WorkflowSeedSource.GLOBAL_OVERRIDE,
                        override_key=override_key,
                    )

        for cube_alias in workflow.stack_order:
            cube = workflow.cubes.get(cube_alias)
            if cube is None:
                continue
            selection = _first_cube_seed(cube_alias, cube)
            if selection is not None:
                return selection

        return WorkflowSeedSelection(seed=None)

    @staticmethod
    def active_global_override_key(workflow: WorkflowSeedState) -> str | None:
        """Return the stored key for an active global seed override."""

        for override_key, override in workflow.global_overrides.items():
            if canonicalize_global_override_key(
                str(override_key)
            ) == SEED_OVERRIDE_KEY and isinstance(override, Mapping):
                return override_key
        return None


def _first_cube_seed(
    cube_alias: str,
    cube: WorkflowSeedCube,
) -> WorkflowSeedSelection | None:
    """Return the first valid seed in one cube's authored surface order."""

    for control in _surface_controls(cube):
        if control.get("input_name") != SEED_OVERRIDE_KEY:
            continue
        control_id = control.get("control_id")
        symbol = control.get("symbol")
        if not isinstance(control_id, str) or not isinstance(symbol, str):
            continue
        value = _node_input_value(cube.buffer, symbol, SEED_OVERRIDE_KEY)
        if not _is_seed(value):
            continue
        return WorkflowSeedSelection(
            seed=value,
            source=WorkflowSeedSource.CUBE_CONTROL,
            cube_alias=cube_alias,
            control_id=control_id,
        )
    return None


def _surface_controls(cube: WorkflowSeedCube) -> tuple[Mapping[str, Any], ...]:
    """Return one cube's authored surface controls."""

    surface = cube.original_cube.get("surface")
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
    """Return one node input value without interpreting malformed state."""

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


def _is_seed(value: object) -> TypeGuard[int]:
    """Return whether a value is an integer seed rather than a boolean."""

    return isinstance(value, int) and not isinstance(value, bool)


__all__ = [
    "SEED_OVERRIDE_KEY",
    "WorkflowSeedAuthority",
    "WorkflowSeedSelection",
    "WorkflowSeedSelector",
    "WorkflowSeedSource",
    "WorkflowSeedState",
]
