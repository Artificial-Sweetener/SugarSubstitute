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

"""Reconcile model-backed global override pickers from prepared snapshots."""

from __future__ import annotations

from substitute.application.model_metadata import model_kind_for_field
from substitute.application.overrides import PinnedOverrideControl
from substitute.application.ports import NodeDefinitionGateway

from .model_choice_snapshot_controller import PanelModelChoiceSnapshotController
from .model_choice_snapshots import PanelModelChoiceSnapshotRequest


def reconcile_model_override_picker(
    *,
    control: PinnedOverrideControl,
    widget: object,
    snapshots: PanelModelChoiceSnapshotController | None,
    node_definitions: NodeDefinitionGateway,
    thumbnail_repository_available: bool,
) -> None:
    """Refresh one model-backed override picker without replacing its widget."""

    spec = control.spec
    reconcile_choice_source = getattr(widget, "reconcile_choice_source", None)
    if not callable(reconcile_choice_source):
        return
    if (
        model_kind_for_field(
            class_type=spec.class_type,
            input_key=spec.field_key,
        )
        is None
    ):
        return
    if snapshots is None:
        return
    snapshot = snapshots.snapshot_for_field(
        PanelModelChoiceSnapshotRequest(
            field_behavior=spec.field_behavior,
            node_name=spec.node_name,
            key=spec.field_key,
            value=control.value,
            node_type=spec.class_type,
            field_type=spec.field_type,
            field_info=spec.field_info,
            node_definition_gateway=node_definitions,
            cube_alias=spec.cube_alias,
            target_model=str(spec.meta_info.get("target_model", "")),
            thumbnail_repository_available=thumbnail_repository_available,
        )
    )
    if snapshot.choice_source is not None:
        reconcile_choice_source(snapshot.choice_source, str(control.value or ""))


__all__ = ["reconcile_model_override_picker"]
