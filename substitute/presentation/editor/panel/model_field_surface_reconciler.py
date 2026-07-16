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

"""Reconcile live model field choices without rebuilding editor projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.application.model_metadata import model_kind_for_field
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.utils import sanitation
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

from .field_registry import EditorFieldIdentity, EditorFieldRegistry
from .field_state_controller import EditorFieldBinding
from .model_choice_snapshot_controller import (
    PanelModelChoiceSnapshot,
    PanelModelChoiceSnapshotRequest,
)

_LOGGER = get_logger("presentation.editor.panel.model_field_surface_reconciler")


class _ModelFieldSurfaceHost(Protocol):
    """Describe panel state needed for targeted model field reconciliation."""

    _cube_states: Mapping[str, object] | None
    _stack_order: Sequence[str] | None
    node_definition_gateway: object

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the behavior snapshot refreshed from current node definitions."""


class _ModelChoiceSnapshotProvider(Protocol):
    """Describe prepared model picker choice construction."""

    def snapshot_for_field(
        self,
        request: PanelModelChoiceSnapshotRequest,
    ) -> PanelModelChoiceSnapshot:
        """Return one prepared model choice snapshot."""


@dataclass(frozen=True, slots=True)
class ModelFieldSurfaceReconciliationResult:
    """Report classes handled in place and classes requiring structural refresh."""

    handled_node_classes: tuple[str, ...]
    fallback_node_classes: tuple[str, ...]
    reconciled_field_count: int


class ModelFieldSurfaceReconciler:
    """Apply refreshed model options to existing picker widgets in place."""

    def __init__(
        self,
        *,
        host: object,
        field_registry: EditorFieldRegistry,
        snapshot_controller: object,
        thumbnail_repository_available: bool,
    ) -> None:
        """Store the panel state and prepared-choice collaborators."""

        self._host = cast(_ModelFieldSurfaceHost, host)
        self._field_registry = field_registry
        self._snapshot_controller = cast(
            _ModelChoiceSnapshotProvider,
            snapshot_controller,
        )
        self._thumbnail_repository_available = thumbnail_repository_available

    def reconcile(
        self,
        refreshed_node_classes: Sequence[str],
    ) -> ModelFieldSurfaceReconciliationResult:
        """Refresh option-only model fields and identify structural fallbacks."""

        normalized_classes = tuple(
            sorted(
                {
                    node_class.strip()
                    for node_class in refreshed_node_classes
                    if isinstance(node_class, str) and node_class.strip()
                }
            )
        )
        snapshot = self._host.current_behavior_snapshot()
        if not normalized_classes or snapshot is None:
            return ModelFieldSurfaceReconciliationResult((), normalized_classes, 0)

        used_classes = self._used_node_classes(normalized_classes)
        expected = self._prepared_picker_snapshots(snapshot, used_classes)
        registered = {
            entry.identity: entry
            for entry in self._field_registry.entries_for_node_classes(used_classes)
            if callable(getattr(entry.widget, "reconcile_choice_source", None))
        }

        handled_classes: set[str] = set()
        fallback_classes: set[str] = set()
        reconciled_count = 0
        for node_class in used_classes:
            expected_for_class = {
                identity: prepared
                for identity, prepared in expected.items()
                if prepared[0].class_type == node_class
            }
            registered_for_class = {
                identity: entry
                for identity, entry in registered.items()
                if entry.binding.node_type == node_class
            }
            if not expected_for_class and not registered_for_class:
                fallback_classes.add(node_class)
                continue
            if set(expected_for_class) != set(registered_for_class):
                fallback_classes.add(node_class)
                continue
            for identity, (field_spec, choice_snapshot) in expected_for_class.items():
                entry = registered_for_class[identity]
                if not self._apply_picker_snapshot(
                    identity=identity,
                    widget=entry.widget,
                    field_spec=field_spec,
                    choice_snapshot=choice_snapshot,
                ):
                    fallback_classes.add(node_class)
                    break
                reconciled_count += 1
            else:
                handled_classes.add(node_class)

        log_debug(
            _LOGGER,
            "Reconciled model field surfaces after node definition refresh",
            refreshed_node_classes=normalized_classes,
            used_node_classes=used_classes,
            handled_node_classes=tuple(sorted(handled_classes)),
            fallback_node_classes=tuple(sorted(fallback_classes)),
            reconciled_field_count=reconciled_count,
        )
        return ModelFieldSurfaceReconciliationResult(
            handled_node_classes=tuple(sorted(handled_classes)),
            fallback_node_classes=tuple(sorted(fallback_classes)),
            reconciled_field_count=reconciled_count,
        )

    def _prepared_picker_snapshots(
        self,
        snapshot: EditorBehaviorSnapshot,
        node_classes: Sequence[str],
    ) -> dict[EditorFieldIdentity, tuple[ResolvedFieldSpec, PanelModelChoiceSnapshot]]:
        """Return expected picker contracts for affected model-backed fields."""

        target_classes = set(node_classes)
        prepared: dict[
            EditorFieldIdentity,
            tuple[ResolvedFieldSpec, PanelModelChoiceSnapshot],
        ] = {}
        for cube_alias, node_specs in snapshot.field_specs_by_alias.items():
            for node_name, field_specs in node_specs.items():
                for field_key, field_spec in field_specs.items():
                    if field_spec.class_type not in target_classes:
                        continue
                    if (
                        model_kind_for_field(
                            class_type=field_spec.class_type,
                            input_key=field_key,
                        )
                        is None
                    ):
                        continue
                    choice_snapshot = self._snapshot_controller.snapshot_for_field(
                        PanelModelChoiceSnapshotRequest(
                            field_behavior=field_spec.field_behavior,
                            node_name=node_name,
                            key=field_key,
                            value=field_spec.value,
                            node_type=field_spec.class_type,
                            field_type=field_spec.field_type,
                            field_info=field_spec.field_info,
                            node_definition_gateway=(
                                self._host.node_definition_gateway
                            ),
                            cube_alias=cube_alias,
                            thumbnail_repository_available=(
                                self._thumbnail_repository_available
                            ),
                        )
                    )
                    if not choice_snapshot.should_build_picker:
                        continue
                    prepared[(cube_alias, node_name, field_key)] = (
                        field_spec,
                        choice_snapshot,
                    )
        return prepared

    def _used_node_classes(
        self,
        refreshed_node_classes: Sequence[str],
    ) -> tuple[str, ...]:
        """Return refreshed classes used by this panel's current cube buffers."""

        target_classes = set(refreshed_node_classes)
        used: set[str] = set()
        cube_states = self._host._cube_states or {}
        for cube_alias in self._host._stack_order or ():
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", None)
            nodes = buffer.get("nodes", {}) if isinstance(buffer, Mapping) else {}
            if not isinstance(nodes, Mapping):
                continue
            for node_data in nodes.values():
                if not isinstance(node_data, Mapping):
                    continue
                node_class = node_data.get("class_type")
                if isinstance(node_class, str) and node_class in target_classes:
                    used.add(node_class)
        return tuple(sorted(used))

    def _apply_picker_snapshot(
        self,
        *,
        identity: EditorFieldIdentity,
        widget: object,
        field_spec: ResolvedFieldSpec,
        choice_snapshot: PanelModelChoiceSnapshot,
    ) -> bool:
        """Replace picker choices and binding metadata without emitting user edits."""

        choice_source = choice_snapshot.choice_source
        reconcile = getattr(widget, "reconcile_choice_source", None)
        if choice_source is None or not callable(reconcile):
            return False
        try:
            reconcile(choice_source, str(field_spec.value or ""))
            self._update_widget_metadata(widget, field_spec)
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to reconcile model picker choices in place",
                cube_alias=identity[0],
                node_name=identity[1],
                field_key=identity[2],
                error_type=type(error).__name__,
            )
            return False
        binding = EditorFieldBinding.from_widget(widget)
        if binding is not None:
            self._field_registry.update_binding(identity, binding)
        return True

    @staticmethod
    def _update_widget_metadata(widget: object, field_spec: ResolvedFieldSpec) -> None:
        """Publish the refreshed resolved field contract on the existing widget."""

        property_getter = getattr(widget, "property", None)
        set_property = getattr(widget, "setProperty", None)
        if not callable(property_getter) or not callable(set_property):
            return
        current = property_getter("input_metadata")
        metadata = dict(current) if isinstance(current, Mapping) else {}
        metadata.update(
            {
                "cube_alias": field_spec.cube_alias,
                "node_name": field_spec.node_name,
                "key": field_spec.field_key,
                "type": field_spec.field_type,
                "meta_info": dict(field_spec.meta_info),
                "field_info": field_spec.field_info,
                "constraints": dict(field_spec.constraints),
                "node_type": field_spec.class_type,
                "resolved_value": field_spec.value,
                "value_source": field_spec.value_source.value,
            }
        )
        set_property("input_metadata", sanitation.deep_sanitize_for_qt(metadata))


__all__ = [
    "ModelFieldSurfaceReconciler",
    "ModelFieldSurfaceReconciliationResult",
]
