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

"""Project production behavior and card state into node audit observations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)
from substitute.application.workflows.editor_projection_service import (
    DIRECT_WORKFLOW_SECTION_KEY,
)
from substitute.presentation.editor.panel.cube_section_build_plan import (
    NodeCardBuildOutcome,
)
from tests.qualification.comfy.bundled_workflows.rendering_audit.models import (
    CardLifecycleObservation,
    CardVisibilityEvent,
    FieldFactoryObservation,
    FieldSpecObservation,
    NodeObservation,
)


class NodeObservationCollector:
    """Project one loaded workflow's node-level production evidence."""

    def collect(
        self,
        *,
        converted_nodes: Mapping[str, Mapping[str, object]],
        snapshot: EditorBehaviorSnapshot,
        outcomes: tuple[NodeCardBuildOutcome, ...],
        cards: Mapping[str, QWidget],
        fields: Mapping[tuple[str, str], QWidget],
        masonry_order: tuple[str, ...],
        factory_observations: tuple[FieldFactoryObservation, ...],
        visibility_events: tuple[CardVisibilityEvent, ...],
    ) -> tuple[NodeObservation, ...]:
        """Assemble production evidence for every converted node identity."""

        behaviors = snapshot.resolved_nodes_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        decisions = snapshot.card_decisions_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        specs_by_node = snapshot.field_specs_by_alias.get(
            DIRECT_WORKFLOW_SECTION_KEY,
            {},
        )
        outcomes_by_node: dict[str, list[NodeCardBuildOutcome]] = {}
        for outcome in outcomes:
            outcomes_by_node.setdefault(outcome.node_name, []).append(outcome)
        factories_by_node: dict[str, list[FieldFactoryObservation]] = {}
        for observation in factory_observations:
            factories_by_node.setdefault(observation.node_id, []).append(observation)
        visibility_by_node: dict[str, list[CardVisibilityEvent]] = {}
        for event in visibility_events:
            visibility_by_node.setdefault(event.node_id, []).append(event)
        masonry_indices = {
            node_id: index for index, node_id in enumerate(masonry_order)
        }
        observations: list[NodeObservation] = []
        for node_id, node_data in converted_nodes.items():
            class_type = str(node_data.get("class_type", ""))
            meta = node_data.get("_meta")
            title = str(meta.get("title", "")) if isinstance(meta, Mapping) else ""
            decision = decisions.get(node_id)
            observations.append(
                NodeObservation(
                    node_id=node_id,
                    class_type=class_type,
                    title=title,
                    behavior_present=node_id in behaviors,
                    decision_present=decision is not None,
                    decision_visible=(
                        bool(decision.visible) if decision is not None else None
                    ),
                    decision_enabled=(
                        bool(decision.enabled) if decision is not None else None
                    ),
                    decision_reason=(
                        str(decision.reason) if decision is not None else ""
                    ),
                    decision_show_enabled_switch=(
                        bool(decision.show_enabled_switch)
                        if decision is not None
                        else None
                    ),
                    field_specs=tuple(
                        self._field_spec_observation(spec)
                        for spec in specs_by_node.get(node_id, {}).values()
                    ),
                    factory_observations=tuple(factories_by_node.get(node_id, ())),
                    build_outcomes=tuple(outcomes_by_node.get(node_id, ())),
                    card=self._card_observation(
                        node_id=node_id,
                        card=cards.get(node_id),
                        fields=fields,
                        masonry_index=masonry_indices.get(node_id),
                        visibility_events=tuple(visibility_by_node.get(node_id, ())),
                    ),
                )
            )
        return tuple(observations)

    @staticmethod
    def _field_spec_observation(spec: ResolvedFieldSpec) -> FieldSpecObservation:
        """Convert one resolved field contract into prompt-safe persisted evidence."""

        behavior = spec.field_behavior
        return FieldSpecObservation(
            field_key=spec.field_key,
            field_type=spec.field_type or "",
            presentation=behavior.presentation.value,
            control_name=behavior.control_name or "",
            hidden=behavior.hidden,
            value_source=spec.value_source.value,
            value_type=type(spec.value).__name__,
            value_repr=_safe_repr(spec.value),
            raw_value_type=type(spec.raw_value).__name__,
            raw_value_repr=_safe_repr(spec.raw_value),
            constraints_repr=_safe_repr(spec.constraints),
            meta_info_repr=_safe_repr(_redacted_mapping(spec.meta_info)),
        )

    @staticmethod
    def _card_observation(
        *,
        node_id: str,
        card: QWidget | None,
        fields: Mapping[tuple[str, str], QWidget],
        masonry_index: int | None,
        visibility_events: tuple[CardVisibilityEvent, ...],
    ) -> CardLifecycleObservation:
        """Read final registry, attachment, visibility, geometry, and field state."""

        field_keys = tuple(
            sorted(
                field_key for field_node, field_key in fields if field_node == node_id
            )
        )
        if card is None:
            return CardLifecycleObservation(
                registered=False,
                widget_type="",
                valid=False,
                parent_type="",
                in_masonry=masonry_index is not None,
                masonry_index=masonry_index,
                visible=False,
                hidden=True,
                base_card_visible=None,
                has_title_controls=None,
                geometry=None,
                registered_field_keys=field_keys,
                visibility_events=visibility_events,
            )
        valid = bool(isValid(card))
        parent = card.parentWidget() if valid else None
        geometry = (
            cast(tuple[int, int, int, int], card.geometry().getRect())
            if valid
            else None
        )
        return CardLifecycleObservation(
            registered=True,
            widget_type=type(card).__name__,
            valid=valid,
            parent_type=type(parent).__name__ if parent is not None else "",
            in_masonry=masonry_index is not None,
            masonry_index=masonry_index,
            visible=card.isVisible() if valid else False,
            hidden=card.isHidden() if valid else True,
            base_card_visible=_optional_bool_property(card, "base_card_visible"),
            has_title_controls=_optional_bool_property(card, "has_title_controls"),
            geometry=geometry,
            registered_field_keys=field_keys,
            visibility_events=visibility_events,
        )


def _optional_bool_property(widget: QWidget, property_name: str) -> bool | None:
    """Return a bool-valued Qt property without interpreting absent state."""

    value = widget.property(property_name)
    return value if isinstance(value, bool) else None


def _safe_repr(value: object, *, limit: int = 2000) -> str:
    """Return a bounded diagnostic representation without raising."""

    try:
        rendered = repr(value)
    except Exception as error:
        rendered = f"<repr failed: {type(error).__name__}: {error}>"
    return rendered if len(rendered) <= limit else f"{rendered[:limit]}…"


def _redacted_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """Redact secret-shaped metadata keys before diagnostic persistence."""

    redacted: dict[str, object] = {}
    for key, item in value.items():
        normalized = str(key).casefold()
        if any(
            term in normalized for term in ("token", "secret", "password", "api_key")
        ):
            redacted[str(key)] = "<redacted>"
        else:
            redacted[str(key)] = item
    return redacted
