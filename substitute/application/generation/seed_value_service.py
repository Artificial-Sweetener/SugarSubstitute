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

"""Capture queued seed evidence and adopt it into live workflow authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.generation.seed_randomization_service import (
    SeedValueChange,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjectionService,
)
from substitute.domain.generation import GenerationSeedValue
from substitute.domain.node_behavior import FieldPresentation
from substitute.domain.workflow import SEED_OVERRIDE_KEY, WorkflowSeedAuthority
from substitute.domain.workflow.override_keys import canonicalize_global_override_key
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.generation.seed_value_service")
_FALLBACK_SEED_KEYS = frozenset({SEED_OVERRIDE_KEY, "variation_seed"})


@dataclass(frozen=True, slots=True)
class SeedAdoptionResult:
    """Describe authoritative workflow seed values changed by one adoption."""

    changes: tuple[SeedValueChange, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether adoption changed at least one live seed owner."""

        return bool(self.changes)


class SeedValueService:
    """Own immutable seed capture and deterministic cross-workflow adoption."""

    def __init__(self) -> None:
        """Create the shared workflow-section projector."""

        self._projection_service = WorkflowEditorProjectionService()

    def capture(
        self,
        *,
        workflow: object,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> tuple[GenerationSeedValue, ...]:
        """Return effective main and variation seed values in stable workflow order."""

        values: list[GenerationSeedValue] = []
        active_override_key = _active_seed_override_key(workflow)
        if active_override_key is not None:
            override = getattr(workflow, "global_overrides", {}).get(
                active_override_key
            )
            if isinstance(override, Mapping):
                value = _seed_int(override.get("value"))
                if value is not None:
                    values.append(
                        GenerationSeedValue(
                            value=value,
                            field_key=SEED_OVERRIDE_KEY,
                            override_key=active_override_key,
                        )
                    )

        projection = self._projection_service.project(workflow)
        captured_identities: set[tuple[str, str, str]] = set()
        if behavior_snapshot is not None:
            for cube_alias, section in projection.entries:
                node_specs = behavior_snapshot.field_specs_by_alias.get(cube_alias, {})
                for node_name, field_specs in node_specs.items():
                    for spec in field_specs.values():
                        if (
                            spec.field_behavior.presentation
                            is not FieldPresentation.SEED_BOX
                        ):
                            continue
                        if active_override_key is not None and _uses_main_override(
                            spec
                        ):
                            continue
                        value = _seed_int(
                            _read_section_value(
                                section,
                                node_name=node_name,
                                field_key=spec.field_key,
                            )
                        )
                        if value is None:
                            continue
                        captured_identities.add((cube_alias, node_name, spec.field_key))
                        values.append(
                            GenerationSeedValue(
                                value=value,
                                field_key=spec.field_key,
                                cube_alias=cube_alias,
                                node_name=node_name,
                                class_type=spec.class_type,
                            )
                        )

        for cube_alias, section in projection.entries:
            for node_name, class_type, field_key, value in _fallback_section_values(
                section
            ):
                if (cube_alias, node_name, field_key) in captured_identities:
                    continue
                if active_override_key is not None and field_key == SEED_OVERRIDE_KEY:
                    continue
                values.append(
                    GenerationSeedValue(
                        value=value,
                        field_key=field_key,
                        cube_alias=cube_alias,
                        node_name=node_name,
                        class_type=class_type,
                    )
                )
        return tuple(values)

    def adopt(
        self,
        *,
        workflow: object,
        behavior_snapshot: EditorBehaviorSnapshot | None,
        source_values: tuple[GenerationSeedValue, ...],
    ) -> SeedAdoptionResult:
        """Load queued seed values into compatible live owners without changing modes."""

        targets = self.capture(
            workflow=workflow,
            behavior_snapshot=behavior_snapshot,
        )
        assignments = _seed_assignments(source_values, targets)
        changes: list[SeedValueChange] = []
        projection = dict(self._projection_service.project(workflow).entries)
        for target, value in assignments:
            if target.override_key is not None:
                overrides = getattr(workflow, "global_overrides", None)
                override = (
                    overrides.get(target.override_key)
                    if isinstance(overrides, dict)
                    else None
                )
                if not isinstance(override, dict):
                    continue
                previous = override.get("value")
                if previous == value:
                    continue
                override["value"] = value
                changes.append(
                    SeedValueChange(
                        value=value,
                        previous_value=previous,
                        override_key=target.override_key,
                    )
                )
                continue
            if target.cube_alias is None or target.node_name is None:
                continue
            section = projection.get(target.cube_alias)
            if section is None:
                continue
            previous = _read_section_value(
                section,
                node_name=target.node_name,
                field_key=target.field_key,
            )
            if not _write_section_value(
                section,
                node_name=target.node_name,
                field_key=target.field_key,
                value=value,
            ):
                continue
            changes.append(
                SeedValueChange(
                    value=value,
                    previous_value=previous,
                    cube_alias=target.cube_alias,
                    node_name=target.node_name,
                    field_key=target.field_key,
                )
            )
        result = SeedAdoptionResult(tuple(changes))
        log_debug(
            _LOGGER,
            "Adopted queued generation seed values",
            source_seed_count=len(source_values),
            target_seed_count=len(targets),
            changed_seed_count=len(changes),
        )
        return result


def _seed_assignments(
    sources: tuple[GenerationSeedValue, ...],
    targets: tuple[GenerationSeedValue, ...],
) -> tuple[tuple[GenerationSeedValue, int], ...]:
    """Match exact identities first, then broadcast or pair within semantic groups."""

    assignments: list[tuple[GenerationSeedValue, int]] = []
    for group in _ordered_groups(targets):
        group_sources = [value for value in sources if _semantic_group(value) == group]
        group_targets = [value for value in targets if _semantic_group(value) == group]
        if not group_sources or not group_targets:
            continue
        if len(group_sources) == 1:
            source_value = group_sources[0].value
            assignments.extend((target, source_value) for target in group_targets)
            continue

        unmatched_sources = list(group_sources)
        unmatched_targets = list(group_targets)
        for identity in (_exact_identity, _node_identity, _class_identity):
            remaining_targets: list[GenerationSeedValue] = []
            for target in unmatched_targets:
                source_index = next(
                    (
                        index
                        for index, source in enumerate(unmatched_sources)
                        if identity(source) == identity(target)
                    ),
                    None,
                )
                if source_index is None:
                    remaining_targets.append(target)
                    continue
                source = unmatched_sources.pop(source_index)
                assignments.append((target, source.value))
            unmatched_targets = remaining_targets

        if not unmatched_targets or not unmatched_sources:
            continue
        assignments.extend(
            (target, source.value)
            for target, source in zip(
                unmatched_targets,
                unmatched_sources,
                strict=False,
            )
        )
    return tuple(assignments)


def _ordered_groups(values: tuple[GenerationSeedValue, ...]) -> tuple[str, ...]:
    """Return distinct semantic groups in target presentation order."""

    return tuple(dict.fromkeys(_semantic_group(value) for value in values))


def _semantic_group(value: GenerationSeedValue) -> str:
    """Keep main seeds separate from each named variation-seed family."""

    if value.override_key is not None or value.field_key == SEED_OVERRIDE_KEY:
        return SEED_OVERRIDE_KEY
    return value.field_key


def _exact_identity(value: GenerationSeedValue) -> tuple[object, ...]:
    """Return the strongest stable identity available for one seed owner."""

    if value.override_key is not None:
        return ("override", canonicalize_global_override_key(value.override_key))
    return (
        "field",
        value.cube_alias,
        value.node_name,
        value.class_type,
        value.field_key,
    )


def _node_identity(value: GenerationSeedValue) -> tuple[object, ...]:
    """Return a cross-workflow identity that tolerates renamed cube aliases."""

    if value.override_key is not None:
        return _exact_identity(value)
    return ("node", value.node_name, value.class_type, value.field_key)


def _class_identity(value: GenerationSeedValue) -> tuple[object, ...]:
    """Return a final structural identity before stable ordinal fallback."""

    if value.override_key is not None:
        return _exact_identity(value)
    return ("class", value.class_type, value.field_key)


def _active_seed_override_key(workflow: object) -> str | None:
    """Return the active global main-seed key for a compatible workflow."""

    try:
        return WorkflowSeedAuthority.active_global_override_key(workflow)  # type: ignore[arg-type]
    except AttributeError:
        return None


def _uses_main_override(spec: object) -> bool:
    """Return whether one seed field participates in the global main-seed override."""

    field_behavior = getattr(spec, "field_behavior", None)
    override_behavior = getattr(field_behavior, "override_behavior", None)
    override_key = getattr(override_behavior, "override_key", None)
    return (
        isinstance(override_key, str)
        and canonicalize_global_override_key(override_key) == SEED_OVERRIDE_KEY
    )


def _fallback_section_values(
    section: object,
) -> tuple[tuple[str, str | None, str, int], ...]:
    """Recover standard seed fields when source behavior metadata is unavailable."""

    buffer = getattr(section, "buffer", None)
    if not isinstance(buffer, Mapping):
        return ()
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return ()
    values: list[tuple[str, str | None, str, int]] = []
    for node_name, node in nodes.items():
        if not isinstance(node_name, str) or not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        class_type_value = node.get("class_type")
        class_type = class_type_value if isinstance(class_type_value, str) else None
        for field_key, raw_value in inputs.items():
            value = _seed_int(raw_value)
            if not isinstance(field_key, str) or field_key not in _FALLBACK_SEED_KEYS:
                continue
            if value is not None:
                values.append((node_name, class_type, field_key, value))
    return tuple(values)


def _read_section_value(
    section: object,
    *,
    node_name: str,
    field_key: str,
) -> object:
    """Read one seed value from a projected workflow section."""

    buffer = getattr(section, "buffer", None)
    if not isinstance(buffer, Mapping):
        return None
    nodes = buffer.get("nodes")
    node = nodes.get(node_name) if isinstance(nodes, Mapping) else None
    inputs = node.get("inputs") if isinstance(node, Mapping) else None
    return inputs.get(field_key) if isinstance(inputs, Mapping) else None


def _write_section_value(
    section: object,
    *,
    node_name: str,
    field_key: str,
    value: int,
) -> bool:
    """Write one seed through the section's canonical mutation boundary."""

    set_editor_value = getattr(section, "set_editor_value", None)
    if callable(set_editor_value):
        return bool(set_editor_value(node_name, field_key=field_key, value=value))
    buffer = getattr(section, "buffer", None)
    nodes = buffer.get("nodes") if isinstance(buffer, dict) else None
    node = nodes.get(node_name) if isinstance(nodes, dict) else None
    inputs = node.get("inputs") if isinstance(node, dict) else None
    if not isinstance(inputs, dict) or inputs.get(field_key) == value:
        return False
    inputs[field_key] = value
    if hasattr(section, "dirty"):
        section.dirty = True
    return True


def _seed_int(value: object) -> int | None:
    """Return an integer seed while rejecting booleans and malformed values."""

    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["SeedAdoptionResult", "SeedValueService"]
