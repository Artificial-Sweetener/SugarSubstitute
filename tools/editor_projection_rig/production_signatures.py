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

"""Analyze settled production editor surfaces for trace correctness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.domain.workflow.models import WorkflowState
from substitute.presentation.editor.panel.view import EditorPanel

from .signatures import (
    CubeSectionSignature,
    EditorSettledSignature,
    FieldSignature,
    NodeCardSignature,
)


def signature_from_panel(
    *, workflow_id: str, workflow: WorkflowState, panel: EditorPanel
) -> EditorSettledSignature:
    """Build a settled signature from rendered panel registries."""

    cube_sections: list[CubeSectionSignature] = []
    card_wrappers = getattr(panel, "card_wrappers", {})
    input_widgets = getattr(panel, "input_widgets_by_field_key", {})
    for alias in workflow.stack_order:
        cube_state = workflow.cubes[alias]
        nodes = cube_state.buffer.get("nodes", {})
        node_cards: list[NodeCardSignature] = []
        if isinstance(nodes, Mapping):
            for node_name in sorted(nodes):
                node_payload = nodes[node_name]
                if not isinstance(node_payload, Mapping):
                    continue
                wrapper = card_wrappers.get((alias, node_name))
                node_cards.append(
                    NodeCardSignature(
                        node_name=str(node_name),
                        node_class=str(node_payload.get("class_type", "")),
                        visible=wrapper is not None,
                        enabled=bool(getattr(wrapper, "isEnabled", lambda: True)()),
                        fields=_field_signatures(
                            alias=alias,
                            node_name=str(node_name),
                            node_payload=node_payload,
                            input_widgets=input_widgets,
                        ),
                    )
                )
        cube_sections.append(
            CubeSectionSignature(
                alias=alias,
                cube_id=cube_state.cube_id,
                version=cube_state.version,
                node_cards=tuple(node_cards),
            )
        )
    return EditorSettledSignature(
        workflow_id=workflow_id,
        cube_sections=tuple(cube_sections),
        parent_chain_violations=tuple(parent_chain_violations(panel)),
    )


def partial_orphan_field_card_refs(signature: Mapping[str, Any]) -> list[str]:
    """Return cards that lost their wrapper after registering visible fields."""

    refs: list[str] = []
    cube_sections = signature.get("cube_sections")
    if not isinstance(cube_sections, Sequence) or isinstance(
        cube_sections, (str, bytes)
    ):
        return refs
    for cube_section in cube_sections:
        if not isinstance(cube_section, Mapping):
            continue
        alias = str(cube_section.get("alias", ""))
        node_cards = cube_section.get("node_cards")
        if not isinstance(node_cards, Sequence) or isinstance(node_cards, (str, bytes)):
            continue
        for node_card in node_cards:
            if not isinstance(node_card, Mapping) or bool(node_card.get("visible")):
                continue
            fields = node_card.get("fields")
            if not isinstance(fields, Sequence) or isinstance(fields, (str, bytes)):
                continue
            if any(
                isinstance(field, Mapping) and bool(field.get("visible"))
                for field in fields
            ):
                refs.append(f"{alias}:{node_card.get('node_name', '')}")
    return sorted(refs)


def parent_chain_violations(panel: EditorPanel) -> list[str]:
    """Return node-card wrappers that are not parented under their cube section."""

    violations: list[str] = []
    card_wrappers = getattr(panel, "card_wrappers", {})
    if not isinstance(card_wrappers, Mapping):
        return violations
    for key, wrapper in card_wrappers.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        alias = str(key[0])
        node_name = str(key[1])
        if isinstance(wrapper, QWidget) and not _has_cube_ancestor(wrapper, alias):
            violations.append(f"{alias}:{node_name}")
    return sorted(violations)


def _field_signatures(
    *,
    alias: str,
    node_name: str,
    node_payload: Mapping[str, Any],
    input_widgets: Mapping[object, object],
) -> tuple[FieldSignature, ...]:
    """Build field signatures from rendered input widgets and runtime inputs."""

    inputs = node_payload.get("inputs", {})
    input_mapping = inputs if isinstance(inputs, Mapping) else {}
    field_keys = {str(key) for key in input_mapping if isinstance(key, str)}
    for key in input_widgets:
        if (
            isinstance(key, tuple)
            and len(key) == 3
            and key[0] == alias
            and key[1] == node_name
            and isinstance(key[2], str)
        ):
            field_keys.add(key[2])
    return tuple(
        FieldSignature(
            field_key=field_key,
            value_repr=repr(input_mapping.get(field_key)),
            visible=input_widgets.get((alias, node_name, field_key)) is not None,
        )
        for field_key in sorted(field_keys)
    )


def _has_cube_ancestor(widget: QWidget, alias: str) -> bool:
    """Return whether a widget has the expected cube section in its parent chain."""

    current = widget.parentWidget()
    while current is not None:
        if current.property("cube_alias") == alias:
            return True
        current = current.parentWidget()
    return False
