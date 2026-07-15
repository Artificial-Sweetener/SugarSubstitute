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

"""Coordinate behavior-driven workflow pinned overrides and toolbar snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable

from substitute.application.node_behavior.models import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)
from substitute.application.node_behavior.list_value_resolver import (
    extract_live_list_options,
    is_choice_field_type,
)
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.node_behavior import OverridePinPolicy
from substitute.domain.workflow.override_keys import canonicalize_global_override_key
from substitute.shared.logging.logger import get_logger, log_debug

from .models import (
    OverrideFieldKey,
    OverrideFieldParticipant,
    OverrideMap,
    OverrideParticipationKind,
    OverrideParticipationSnapshot,
    OverrideSelectionMap,
    OverrideToolbarCandidate,
    OverrideToolbarSnapshot,
    OverrideValue,
    PinnedOverrideControl,
)

_LOGGER = get_logger("application.overrides.pinned_override_service")


def _compact_log_value(value: Any) -> str:
    """Return a compact representation for structured override logging."""

    rendered = repr(value)
    if len(rendered) > 240:
        return f"{rendered[:237]}..."
    return rendered


class PinnedOverrideService:
    """Own canonical workflow override state, toolbar snapshots, and workflow writes."""

    DEFAULT_MODE = "global"

    def canonicalize_override_key(self, override_key: str) -> str:
        """Return the canonical persisted override key for one field alias."""

        return canonicalize_global_override_key(override_key)

    def normalize_workflow_overrides(
        self,
        raw_overrides: dict[str, Any] | None,
    ) -> OverrideMap:
        """Normalize persisted override payloads into the canonical runtime map."""

        log_debug(
            _LOGGER,
            "normalize workflow overrides started",
            raw_override_keys=tuple(sorted(str(key) for key in (raw_overrides or {}))),
        )
        normalized: OverrideMap = {}
        for key, value in (raw_overrides or {}).items():
            canonical_key = self.canonicalize_override_key(str(key))
            normalized[canonical_key] = (
                dict(value)
                if isinstance(value, dict)
                else {"value": value, "mode": self.DEFAULT_MODE}
            )
            log_debug(
                _LOGGER,
                "normalized workflow override",
                raw_key=str(key),
                canonical_key=canonical_key,
                normalized_value=_compact_log_value(
                    normalized[canonical_key].get("value")
                ),
                normalized_mode=normalized[canonical_key].get("mode"),
            )
        log_debug(
            _LOGGER,
            "normalize workflow overrides completed",
            normalized_override_keys=tuple(sorted(normalized)),
        )
        return normalized

    def normalize_workflow_selections(
        self,
        raw_selections: Mapping[str, object] | None,
    ) -> OverrideSelectionMap:
        """Normalize persisted override menu selections into canonical runtime state."""

        normalized: OverrideSelectionMap = {}
        for key, selected in (raw_selections or {}).items():
            if not isinstance(selected, bool):
                continue
            normalized[self.canonicalize_override_key(str(key))] = selected
        log_debug(
            _LOGGER,
            "normalize workflow override selections completed",
            raw_selection_keys=tuple(
                sorted(str(key) for key in (raw_selections or {}))
            ),
            normalized_selections=tuple(
                {"override_key": key, "selected": selected}
                for key, selected in sorted(normalized.items())
            ),
        )
        return normalized

    def build_toolbar_snapshot(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
        overrides: OverrideMap,
    ) -> OverrideToolbarSnapshot:
        """Build the deterministic toolbar snapshot for one editor refresh pass."""

        stack_order_tuple = tuple(stack_order)
        candidates = self._build_candidates(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order_tuple,
        )
        log_debug(
            _LOGGER,
            "build toolbar snapshot candidates",
            stack_order=stack_order_tuple,
            override_keys=tuple(sorted(overrides)),
            candidate_count=len(candidates),
            candidates=tuple(
                {
                    "override_key": candidate.override_key,
                    "label": candidate.label,
                    "pin_policy": candidate.pin_policy.value,
                    "toolbar_order": candidate.toolbar_order,
                    "representative_cube": candidate.representative_spec.cube_alias,
                    "representative_node": candidate.representative_spec.node_name,
                    "representative_class": candidate.representative_spec.class_type,
                    "representative_field": candidate.representative_spec.field_key,
                    "representative_value": _compact_log_value(
                        candidate.representative_spec.value
                    ),
                }
                for candidate in candidates
            ),
        )
        active_controls = [
            PinnedOverrideControl(
                override_key=candidate.override_key,
                label=candidate.label,
                value=overrides[candidate.override_key].get("value"),
                spec=candidate.representative_spec,
            )
            for candidate in candidates
            if candidate.override_key in overrides
        ]
        log_debug(
            _LOGGER,
            "build toolbar snapshot active controls",
            active_control_count=len(active_controls),
            active_controls=tuple(
                {
                    "override_key": control.override_key,
                    "label": control.label,
                    "value": _compact_log_value(control.value),
                    "representative_cube": control.spec.cube_alias,
                    "representative_node": control.spec.node_name,
                    "representative_class": control.spec.class_type,
                    "representative_field": control.spec.field_key,
                    "spec_value": _compact_log_value(control.spec.value),
                    "spec_raw_value": _compact_log_value(control.spec.raw_value),
                    "spec_value_source": control.spec.value_source.value,
                }
                for control in active_controls
            ),
        )
        return OverrideToolbarSnapshot(
            candidates=candidates,
            active_controls=active_controls,
            active_override_keys=tuple(
                control.override_key for control in active_controls
            ),
        )

    def build_participation_snapshot(
        self,
        *,
        overrides: OverrideMap,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
    ) -> OverrideParticipationSnapshot:
        """Return field-level participants for active global overrides."""

        stack_order_tuple = tuple(stack_order)
        active_keys = frozenset(
            self.canonicalize_override_key(key) for key in overrides
        )
        eligible_specs_by_key: dict[str, list[ResolvedFieldSpec]] = {
            key: [] for key in active_keys
        }
        eligible_fields_by_key: dict[str, list[OverrideFieldKey]] = {
            key: [] for key in active_keys
        }
        for alias in stack_order_tuple:
            per_node = behavior_snapshot.field_specs_by_alias.get(alias, {})
            for node_name, field_specs in per_node.items():
                for spec in field_specs.values():
                    override_key = self._participating_spec_override_key(spec)
                    if override_key is None:
                        continue
                    canonical_key = self.canonicalize_override_key(override_key)
                    if canonical_key not in active_keys:
                        continue
                    eligible_specs_by_key.setdefault(canonical_key, []).append(spec)
                    eligible_fields_by_key.setdefault(canonical_key, []).append(
                        (alias, node_name, spec.field_key)
                    )

        participants_by_key: dict[str, tuple[OverrideFieldParticipant, ...]] = {}
        for override_key, specs in eligible_specs_by_key.items():
            if not specs:
                participants_by_key[override_key] = ()
                continue
            authority = specs[0]
            override_value = overrides.get(override_key, {}).get("value")
            participants = self._participants_for_authority(
                override_key=override_key,
                authority=authority,
                specs=specs,
                override_value=override_value,
            )
            participants_by_key[override_key] = participants

        log_debug(
            _LOGGER,
            "built override participation snapshot",
            override_keys=tuple(sorted(active_keys)),
            participation_summary=tuple(
                {
                    "override_key": key,
                    "eligible_count": len(eligible_fields_by_key.get(key, ())),
                    "participant_count": len(participants_by_key.get(key, ())),
                    "skipped_count": len(eligible_fields_by_key.get(key, ()))
                    - len(participants_by_key.get(key, ())),
                }
                for key in sorted(active_keys)
            ),
        )
        return OverrideParticipationSnapshot(
            participants_by_key=participants_by_key,
            eligible_fields_by_key={
                key: tuple(fields) for key, fields in eligible_fields_by_key.items()
            },
        )

    def build_serialization_scopes(
        self,
        *,
        overrides: OverrideMap,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
    ) -> dict[str, GlobalOverrideSerializationScope]:
        """Return SugarScript serialization scopes for active global overrides."""

        participation_snapshot = self.build_participation_snapshot(
            overrides=overrides,
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        )
        scopes: dict[str, GlobalOverrideSerializationScope] = {}
        for override_key, override in overrides.items():
            if not isinstance(override, Mapping):
                continue
            canonical_key = self.canonicalize_override_key(str(override_key))
            participants = participation_snapshot.participants_by_key.get(
                canonical_key,
                (),
            )
            eligible_fields = frozenset(
                participation_snapshot.eligible_fields_by_key.get(canonical_key, ())
            )
            participant_fields = frozenset(
                participant.field_identity for participant in participants
            )
            scopes[canonical_key] = GlobalOverrideSerializationScope(
                override_key=canonical_key,
                value=override.get("value"),
                mode=str(override.get("mode") or self.DEFAULT_MODE),
                full_participation=bool(eligible_fields)
                and participant_fields == eligible_fields,
                participant_fields=participant_fields,
            )
        log_debug(
            _LOGGER,
            "built override serialization scopes",
            scope_summary=tuple(
                {
                    "override_key": key,
                    "full_participation": scope.full_participation,
                    "participant_count": len(scope.participant_fields),
                }
                for key, scope in sorted(scopes.items())
            ),
        )
        return scopes

    def materialize_default_overrides(
        self,
        *,
        overrides: OverrideMap,
        selections: OverrideSelectionMap | None = None,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
    ) -> bool:
        """Materialize default-pinned overrides that are absent from persisted state."""

        changed = False
        selection_map = selections or {}
        stack_order_tuple = tuple(stack_order)
        log_debug(
            _LOGGER,
            "materialize default overrides started",
            existing_override_keys=tuple(sorted(overrides)),
            selection_keys=tuple(sorted(selection_map)),
            stack_order=stack_order_tuple,
        )
        for candidate in self._build_candidates(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order_tuple,
        ):
            if candidate.pin_policy != OverridePinPolicy.DEFAULT_PINNED:
                continue
            if selection_map.get(candidate.override_key) is False:
                log_debug(
                    _LOGGER,
                    "default override materialization skipped by user selection",
                    override_key=candidate.override_key,
                    representative_cube=candidate.representative_spec.cube_alias,
                    representative_node=candidate.representative_spec.node_name,
                    representative_class=candidate.representative_spec.class_type,
                    representative_field=candidate.representative_spec.field_key,
                )
                continue
            if candidate.override_key in overrides:
                log_debug(
                    _LOGGER,
                    "default override already materialized",
                    override_key=candidate.override_key,
                    existing_value=_compact_log_value(
                        overrides[candidate.override_key].get("value")
                    ),
                    representative_cube=candidate.representative_spec.cube_alias,
                    representative_node=candidate.representative_spec.node_name,
                    representative_class=candidate.representative_spec.class_type,
                    representative_field=candidate.representative_spec.field_key,
                )
                continue
            initial_value = self._initial_override_value(candidate.representative_spec)
            log_debug(
                _LOGGER,
                "materializing default override",
                override_key=candidate.override_key,
                initial_value=_compact_log_value(initial_value),
                representative_cube=candidate.representative_spec.cube_alias,
                representative_node=candidate.representative_spec.node_name,
                representative_class=candidate.representative_spec.class_type,
                representative_field=candidate.representative_spec.field_key,
            )
            self.set_override_value(
                overrides,
                candidate.override_key,
                initial_value,
            )
            changed = True
        log_debug(
            _LOGGER,
            "materialize default overrides completed",
            changed=changed,
            final_override_keys=tuple(sorted(overrides)),
        )
        return changed

    def pin_override(
        self,
        *,
        overrides: OverrideMap,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
        override_key: str,
    ) -> bool:
        """Activate one override key in workflow state when a candidate exists."""

        canonical_key = self.canonicalize_override_key(override_key)
        stack_order_tuple = tuple(stack_order)
        log_debug(
            _LOGGER,
            "pin override requested",
            requested_key=override_key,
            canonical_key=canonical_key,
            existing_override_keys=tuple(sorted(overrides)),
            stack_order=stack_order_tuple,
        )
        if canonical_key in overrides:
            return False
        candidate = self._candidate_by_key(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order_tuple,
            override_key=canonical_key,
        )
        if candidate is None:
            log_debug(
                _LOGGER,
                "pin override skipped missing candidate",
                requested_key=override_key,
                canonical_key=canonical_key,
            )
            return False
        self.set_override_value(
            overrides,
            canonical_key,
            self._initial_override_value(candidate.representative_spec),
        )
        return True

    def unpin_override(self, overrides: OverrideMap, override_key: str) -> bool:
        """Deactivate one override key when present in workflow state."""

        canonical_key = self.canonicalize_override_key(override_key)
        log_debug(
            _LOGGER,
            "unpin override requested",
            requested_key=override_key,
            canonical_key=canonical_key,
            existing_override_keys=tuple(sorted(overrides)),
        )
        if canonical_key not in overrides:
            return False
        overrides.pop(canonical_key, None)
        return True

    def set_override_value(
        self,
        overrides: OverrideMap,
        override_key: str,
        value: Any,
        *,
        mode: str = DEFAULT_MODE,
    ) -> None:
        """Persist one canonical override value into the workflow override map."""

        canonical_key = self.canonicalize_override_key(override_key)
        log_debug(
            _LOGGER,
            "set override value",
            requested_key=override_key,
            canonical_key=canonical_key,
            value=_compact_log_value(value),
            mode=mode,
        )
        overrides[canonical_key] = {
            "value": value,
            "mode": mode,
        }

    def apply_overrides_to_workflow(
        self,
        *,
        overrides: OverrideMap,
        workflow: Any | None,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> bool:
        """Apply active overrides and return whether workflow inputs changed."""

        workflow_stack_order = tuple(getattr(workflow, "stack_order", ()))
        log_debug(
            _LOGGER,
            "apply overrides to workflow started",
            workflow_present=workflow is not None,
            has_cubes=bool(workflow is not None and hasattr(workflow, "cubes")),
            behavior_snapshot_present=behavior_snapshot is not None,
            override_keys=tuple(sorted(overrides)),
            stack_order=workflow_stack_order,
        )
        if workflow is None or not hasattr(workflow, "cubes"):
            return False
        if behavior_snapshot is None:
            return self._apply_overrides_without_snapshot(
                overrides=overrides, workflow=workflow
            )

        participation_snapshot = self.build_participation_snapshot(
            overrides=overrides,
            behavior_snapshot=behavior_snapshot,
            stack_order=getattr(workflow, "stack_order", []),
        )
        participant_fields = participation_snapshot.participant_fields()
        changed = False
        for alias in getattr(workflow, "stack_order", []):
            cube_state = getattr(workflow, "cubes", {}).get(alias)
            if cube_state is None:
                continue
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            for node_name, field_specs in behavior_snapshot.field_specs_by_alias.get(
                alias,
                {},
            ).items():
                node_payload = nodes.get(node_name, {})
                inputs = (
                    node_payload.get("inputs", {})
                    if isinstance(node_payload, dict)
                    else {}
                )
                if not isinstance(inputs, dict):
                    continue
                for spec in field_specs.values():
                    override_key = self._participating_spec_override_key(spec)
                    if override_key is None:
                        continue
                    canonical_key = self.canonicalize_override_key(override_key)
                    override = overrides.get(canonical_key)
                    if override is None:
                        continue
                    if (alias, node_name, spec.field_key) not in participant_fields:
                        log_debug(
                            _LOGGER,
                            "skip override field without participation",
                            cube_alias=alias,
                            node_name=node_name,
                            class_type=spec.class_type,
                            field_key=spec.field_key,
                            canonical_key=canonical_key,
                            new_value=_compact_log_value(override.get("value")),
                        )
                        continue
                    old_value = inputs.get(spec.field_key)
                    new_value = override.get("value")
                    log_debug(
                        _LOGGER,
                        "apply override field",
                        cube_alias=alias,
                        node_name=node_name,
                        class_type=spec.class_type,
                        field_key=spec.field_key,
                        requested_override_key=override_key,
                        canonical_key=canonical_key,
                        old_value=_compact_log_value(old_value),
                        new_value=_compact_log_value(new_value),
                        spec_value=_compact_log_value(spec.value),
                        spec_raw_value=_compact_log_value(spec.raw_value),
                        spec_value_source=spec.value_source.value,
                    )
                    if old_value != new_value:
                        inputs[spec.field_key] = new_value
                        changed = True
        return changed

    def _participants_for_authority(
        self,
        *,
        override_key: str,
        authority: ResolvedFieldSpec,
        specs: Iterable[ResolvedFieldSpec],
        override_value: Any,
    ) -> tuple[OverrideFieldParticipant, ...]:
        """Return participants for one active override and authority field."""

        if not is_choice_field_type(authority.field_type):
            return tuple(
                OverrideFieldParticipant(
                    override_key=override_key,
                    cube_alias=spec.cube_alias,
                    node_name=spec.node_name,
                    field_key=spec.field_key,
                    participation=OverrideParticipationKind.NON_CHOICE,
                )
                for spec in specs
            )

        authority_options = extract_live_list_options(authority.field_info)
        if not authority_options:
            return ()
        if (
            not isinstance(override_value, str)
            or override_value not in authority_options
        ):
            return ()

        participants: list[OverrideFieldParticipant] = []
        for spec in specs:
            spec_options = extract_live_list_options(spec.field_info)
            if not spec_options:
                continue
            participation: OverrideParticipationKind | None = None
            if spec_options == authority_options:
                participation = OverrideParticipationKind.EXACT_OPTIONS
            elif isinstance(override_value, str) and override_value in spec_options:
                participation = OverrideParticipationKind.VALUE_SUPPORTED
            if participation is None:
                continue
            participants.append(
                OverrideFieldParticipant(
                    override_key=override_key,
                    cube_alias=spec.cube_alias,
                    node_name=spec.node_name,
                    field_key=spec.field_key,
                    participation=participation,
                )
            )
        return tuple(participants)

    def _build_candidates(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
    ) -> list[OverrideToolbarCandidate]:
        """Collect deterministic toolbar candidates from resolved field specs."""

        representative_specs: dict[str, ResolvedFieldSpec] = {}
        labels: dict[str, str] = {}
        pin_policies: dict[str, OverridePinPolicy] = {}
        toolbar_orders: dict[str, int | None] = {}

        for alias in stack_order:
            per_node = behavior_snapshot.field_specs_by_alias.get(alias, {})
            for field_specs in per_node.values():
                for spec in field_specs.values():
                    override_behavior = spec.field_behavior.override_behavior
                    override_key = override_behavior.override_key
                    if (
                        not isinstance(override_key, str)
                        or override_behavior.pin_policy == OverridePinPolicy.NEVER
                    ):
                        continue
                    if is_choice_field_type(
                        spec.field_type
                    ) and not extract_live_list_options(spec.field_info):
                        continue
                    canonical_key = self.canonicalize_override_key(override_key)
                    if canonical_key not in representative_specs:
                        representative_specs[canonical_key] = spec
                        labels[canonical_key] = (
                            override_behavior.toolbar_label_override or canonical_key
                        )
                        pin_policies[canonical_key] = override_behavior.pin_policy
                        toolbar_orders[canonical_key] = override_behavior.toolbar_order

        candidates = [
            OverrideToolbarCandidate(
                override_key=override_key,
                label=labels[override_key],
                pin_policy=pin_policies[override_key],
                toolbar_order=toolbar_orders[override_key],
                representative_spec=representative_specs[override_key],
            )
            for override_key in representative_specs
        ]
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.toolbar_order
                if candidate.toolbar_order is not None
                else 1_000_000,
                candidate.label.casefold(),
                candidate.override_key.casefold(),
            ),
        )

    def _candidate_by_key(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Iterable[str],
        override_key: str,
    ) -> OverrideToolbarCandidate | None:
        """Return the toolbar candidate for one canonical override key when present."""

        for candidate in self._build_candidates(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
        ):
            if candidate.override_key == override_key:
                return candidate
        return None

    @staticmethod
    def _participating_spec_override_key(spec: ResolvedFieldSpec) -> str | None:
        """Return the override key for an explicitly participating field spec."""

        override_behavior = spec.field_behavior.override_behavior
        override_key = override_behavior.override_key
        if (
            not isinstance(override_key, str)
            or override_behavior.pin_policy == OverridePinPolicy.NEVER
        ):
            return None
        return override_key

    @staticmethod
    def _initial_override_value(spec: ResolvedFieldSpec) -> Any:
        """Return the representative runtime value used for first pin materialization."""

        value = spec.value
        if isinstance(value, dict) and "value" in value:
            return value.get("value")
        return value

    def _apply_overrides_without_snapshot(
        self,
        *,
        overrides: OverrideMap,
        workflow: Any,
    ) -> bool:
        """Apply overrides without a snapshot and return whether inputs changed."""

        changed = False
        for cube in getattr(workflow, "cubes", {}).values():
            nodes = getattr(cube, "buffer", {}).get("nodes", {})
            for node in nodes.values():
                if not isinstance(node, dict):
                    continue
                inputs = node.get("inputs", {})
                if not isinstance(inputs, dict):
                    continue
                for override_key, override in overrides.items():
                    if override_key in inputs:
                        log_debug(
                            _LOGGER,
                            "apply override without snapshot field",
                            override_key=override_key,
                            old_value=_compact_log_value(inputs.get(override_key)),
                            new_value=_compact_log_value(override.get("value")),
                        )
                        new_value = override.get("value")
                        if inputs.get(override_key) != new_value:
                            inputs[override_key] = new_value
                            changed = True
        return changed


__all__ = ["OverrideMap", "OverrideValue", "PinnedOverrideService"]
