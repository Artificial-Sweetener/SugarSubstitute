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

"""Randomize workflow-owned seed values before generation serialization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import random
from typing import cast

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjectionService,
)
from substitute.domain.generation.seed_control import (
    SeedControlState,
    SeedMode,
)
from substitute.domain.node_behavior import FieldPresentation
from substitute.domain.workflow import (
    SEED_OVERRIDE_KEY,
    WorkflowSeedAuthority,
    WorkflowState,
)
from substitute.domain.workflow.override_keys import canonicalize_global_override_key
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.generation.seed_randomization_service")
DEFAULT_RANDOM_SEED_MAX = 18_446_744_073_709_551_615
SEED_FIELD_KEY = SEED_OVERRIDE_KEY


@dataclass(frozen=True, slots=True)
class SeedValueChange:
    """Describe one authoritative seed value changed for generation."""

    value: int
    previous_value: object
    cube_alias: str | None = None
    node_name: str | None = None
    field_key: str = SEED_FIELD_KEY
    override_key: str | None = None


@dataclass(frozen=True, slots=True)
class SeedRandomizationResult:
    """Return all authoritative seed changes from one generation preparation."""

    changes: tuple[SeedValueChange, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether any effective seed owner changed."""

        return bool(self.changes)


class SeedRandomizationService:
    """Randomize workflow-owned seed values according to persisted seed modes."""

    def __init__(self) -> None:
        """Create the shared editor-section projector used by every workflow kind."""

        self._editor_projection_service = WorkflowEditorProjectionService()

    def randomize_workflow_seeds(
        self,
        *,
        workflow: WorkflowState,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        randint: Callable[[int, int], int] = random.randint,
    ) -> SeedRandomizationResult:
        """Randomize effective workflow seed owners and return their changes."""

        cube_changes = self._randomize_cube_seeds(
            workflow=workflow,
            behavior_snapshot=behavior_snapshot,
            randint=randint,
        )
        override_changes = self._randomize_override_seeds(
            workflow=workflow,
            behavior_snapshot=behavior_snapshot,
            randint=randint,
        )
        return SeedRandomizationResult(cube_changes + override_changes)

    def _randomize_cube_seeds(
        self,
        *,
        workflow: WorkflowState,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        randint: Callable[[int, int], int],
    ) -> tuple[SeedValueChange, ...]:
        """Randomize node-card seed fields identified by the behavior snapshot."""

        if behavior_snapshot is None:
            return ()
        changes: list[SeedValueChange] = []
        override_seed_active = WorkflowSeedAuthority.active_global_override_key(
            workflow
        )
        projection = self._editor_projection_service.project(workflow)
        for cube_alias, cube in projection.entries:
            node_specs = behavior_snapshot.field_specs_by_alias.get(cube_alias, {})
            for node_name, field_specs in node_specs.items():
                for spec in field_specs.values():
                    if (
                        spec.field_behavior.presentation
                        is not FieldPresentation.SEED_BOX
                    ):
                        continue
                    if override_seed_active is not None and _spec_uses_seed_override(
                        spec
                    ):
                        continue
                    if (
                        self._field_seed_mode(cube, node_name, spec.field_key).mode
                        == SeedMode.FIXED
                    ):
                        continue
                    bounds = _seed_bounds(spec.constraints)
                    if bounds is None:
                        log_warning(
                            _LOGGER,
                            "Skipped field seed randomization for invalid seed range",
                            cube_alias=cube_alias,
                            node_name=node_name,
                            field_key=spec.field_key,
                        )
                        continue
                    seed_value = randint(*bounds)
                    previous_value = _read_section_input_seed(
                        cube,
                        node_name=node_name,
                        field_key=spec.field_key,
                    )
                    if _write_section_input_seed(
                        cube,
                        node_name=node_name,
                        field_key=spec.field_key,
                        seed_value=seed_value,
                    ):
                        changes.append(
                            SeedValueChange(
                                cube_alias=cube_alias,
                                node_name=node_name,
                                field_key=spec.field_key,
                                previous_value=previous_value,
                                value=seed_value,
                            )
                        )
                        log_debug(
                            _LOGGER,
                            "Randomized field seed",
                            cube_alias=cube_alias,
                            node_name=node_name,
                            field_key=spec.field_key,
                            seed_value=seed_value,
                        )
        return tuple(changes)

    def _randomize_override_seeds(
        self,
        *,
        workflow: WorkflowState,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        randint: Callable[[int, int], int],
    ) -> tuple[SeedValueChange, ...]:
        """Randomize global seed override values using workflow-owned mode state."""

        changes: list[SeedValueChange] = []
        constraints = self._override_seed_constraints(behavior_snapshot)
        for override_key, override in workflow.global_overrides.items():
            canonical_key = canonicalize_global_override_key(str(override_key))
            if canonical_key != SEED_FIELD_KEY or not isinstance(override, dict):
                continue
            if self._override_seed_mode(workflow, canonical_key).mode == SeedMode.FIXED:
                continue
            bounds = _seed_bounds(constraints)
            if bounds is None:
                log_warning(
                    _LOGGER,
                    "Skipped override seed randomization for invalid seed range",
                    override_key=canonical_key,
                )
                continue
            seed_value = randint(*bounds)
            previous_value = override.get("value")
            if previous_value == seed_value:
                continue
            override["value"] = seed_value
            changes.append(
                SeedValueChange(
                    override_key=canonical_key,
                    previous_value=previous_value,
                    value=seed_value,
                )
            )
            log_debug(
                _LOGGER,
                "Randomized override seed",
                override_key=canonical_key,
                seed_value=seed_value,
            )
        return tuple(changes)

    @staticmethod
    def _field_seed_mode(
        section: object,
        node_name: str,
        field_key: str,
    ) -> SeedControlState:
        """Return persisted mode for a section seed field, defaulting to random."""

        states = getattr(section, "field_control_states", None)
        if not isinstance(states, dict):
            return SeedControlState()
        node_states = states.get(node_name)
        if not isinstance(node_states, dict):
            return SeedControlState()
        state = node_states.get(field_key)
        return state if isinstance(state, SeedControlState) else SeedControlState()

    @staticmethod
    def _override_seed_mode(
        workflow: WorkflowState,
        override_key: str,
    ) -> SeedControlState:
        """Return persisted seed mode for a global override, defaulting to random."""

        state = workflow.override_control_states.get(override_key)
        return state if isinstance(state, SeedControlState) else SeedControlState()

    @staticmethod
    def _override_seed_constraints(
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> Mapping[str, object]:
        """Return representative constraints for the global seed override."""

        if behavior_snapshot is None:
            return {}
        for node_specs in behavior_snapshot.field_specs_by_alias.values():
            for field_specs in node_specs.values():
                spec = field_specs.get(SEED_FIELD_KEY)
                if spec is not None:
                    return cast(Mapping[str, object], spec.constraints)
        return {}


def _spec_uses_seed_override(spec: object) -> bool:
    """Return whether one seed field participates in the global seed override."""

    field_behavior = getattr(spec, "field_behavior", None)
    override_behavior = getattr(field_behavior, "override_behavior", None)
    override_key = getattr(override_behavior, "override_key", None)
    return (
        isinstance(override_key, str)
        and canonicalize_global_override_key(override_key) == SEED_FIELD_KEY
    )


def _seed_bounds(constraints: Mapping[str, object]) -> tuple[int, int] | None:
    """Return random seed bounds from a field constraint mapping."""

    minimum = _coerce_int(constraints.get("min"), default=0)
    maximum = _coerce_int(constraints.get("max"), default=DEFAULT_RANDOM_SEED_MAX)
    if maximum < minimum:
        return None
    return minimum, maximum


def _coerce_int(value: object, *, default: int) -> int:
    """Coerce a seed bound while preserving safe defaults."""

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


def _write_section_input_seed(
    section: object,
    *,
    node_name: str,
    field_key: str,
    seed_value: int,
) -> bool:
    """Write one seed through its workflow section's canonical mutation boundary."""

    set_editor_value = getattr(section, "set_editor_value", None)
    if callable(set_editor_value):
        return bool(
            set_editor_value(
                node_name,
                field_key=field_key,
                value=seed_value,
            )
        )
    buffer = getattr(section, "buffer", None)

    if not isinstance(buffer, dict):
        return False
    nodes = buffer.get("nodes")
    if not isinstance(nodes, dict):
        nodes = {}
        buffer["nodes"] = nodes
    node = nodes.get(node_name)
    if not isinstance(node, dict):
        node = {}
        nodes[node_name] = node
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
        node["inputs"] = inputs
    if inputs.get(field_key) == seed_value:
        return False
    inputs[field_key] = seed_value
    if hasattr(section, "dirty"):
        section.dirty = True
    return True


def _read_section_input_seed(
    section: object,
    *,
    node_name: str,
    field_key: str,
) -> object:
    """Return one current field seed without changing malformed section state."""

    buffer = getattr(section, "buffer", None)
    if not isinstance(buffer, Mapping):
        return None
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(node_name)
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(field_key)


__all__ = [
    "DEFAULT_RANDOM_SEED_MAX",
    "SeedRandomizationResult",
    "SeedRandomizationService",
    "SeedValueChange",
]
