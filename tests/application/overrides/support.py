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

"""Contract tests for the application pinned override service."""

from __future__ import annotations


from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)


def _field_spec(
    *,
    cube_alias: str,
    node_name: str,
    class_type: str,
    field_key: str,
    value: object,
    override_key: str | None,
    pin_policy: OverridePinPolicy,
    toolbar_order: int | None = None,
    toolbar_label: str | None = None,
    field_type: str = "STRING",
    field_info: list[object] | None = None,
) -> ResolvedFieldSpec:
    """Build one resolved field spec for focused pinned-override assertions."""

    return ResolvedFieldSpec(
        cube_alias=cube_alias,
        node_name=node_name,
        class_type=class_type,
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={"cube_alias": cube_alias},
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=pin_policy,
                toolbar_label_override=toolbar_label,
                toolbar_order=toolbar_order,
            ),
        ),
    )


def _snapshot(
    field_specs_by_alias: dict[str, dict[str, dict[str, ResolvedFieldSpec]]],
) -> EditorBehaviorSnapshot:
    """Build the minimal behavior snapshot required by override service tests."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias=field_specs_by_alias,
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )
