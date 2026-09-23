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

"""Publish composed Input-canvas owners on the legacy shell boundary."""

from __future__ import annotations

from typing import Any


def publish_input_canvas_composition(
    shell: Any,
    composition: Any,
    input_node_preview_coordinator: Any,
) -> None:
    """Expose focused Input owners through the host-facing shell contract."""

    shell.input_image_materialization_service = (
        composition.input_image_materialization_service
    )
    shell.input_section_materialization_service = (
        composition.input_section_materialization_service
    )
    shell.input_canvas_bindings = composition.input_canvas_bindings
    shell.input_asset_associations = composition.input_asset_associations
    shell.input_mask_selection_service = composition.input_mask_selection_service
    shell.ordered_mask_region_authoring_service = (
        composition.ordered_mask_region_authoring_service
    )
    shell.workflow_input_canvas_duplication_service = (
        composition.workflow_input_canvas_duplication_service
    )
    shell.input_canvas_authority_reconciliation_service = (
        composition.input_canvas_authority_reconciliation_service
    )
    shell.input_canvas_tool_controller = composition.input_canvas_tool_controller
    shell.input_canvas_tool_profile_controller = (
        composition.input_canvas_tool_profile_controller
    )
    shell.input_shared_edge_resize_policy = composition.input_shared_edge_resize_policy
    shell.input_scene_mapping_changes = composition.input_scene_mapping_changes
    shell.input_canvas_shell_adapter = composition.input_canvas_shell_adapter
    shell.input_image_materialization_presenter = composition.input_presentation.images
    shell.input_mask_picker_presenter = composition.input_presentation.pickers
    shell.input_mask_selection_presenter = composition.input_presentation.masks
    shell.input_node_preview_coordinator = input_node_preview_coordinator
    shell.input_node_interaction_controller = (
        composition.input_node_interaction_controller
    )
    shell.input_mask_visual_opacity_controller = (
        composition.input_mask_visual_opacity_controller
    )
    shell.input_document_change_observer = composition.input_document_change_observer
    shell.input_editable_document_change_tracker = (
        composition.input_editable_document_change_tracker
    )
    shell.input_generation_snapshot_service = (
        composition.input_generation_snapshot_service
    )
    shell.input_editable_document_lifecycle = (
        composition.input_editable_document_lifecycle
    )
    shell.input_canvas_capability_service = composition.input_canvas_capability_service
    shell.regional_interaction_coordinator = (
        composition.regional_interaction_coordinator
    )
    shell.restored_ordered_mask_collections = (
        composition.restored_ordered_mask_collections
    )
    shell.synthetic_canvas_resolution_role_service = (
        composition.synthetic_canvas_resolution_role_service
    )
    shell.synthetic_canvas_resolution_transaction_service = (
        composition.synthetic_canvas_resolution_transaction_service
    )
    shell.synthetic_canvas_geometry_adapter = (
        composition.synthetic_canvas_geometry_adapter
    )
    shell.synthetic_canvas_resolution_controller = (
        composition.synthetic_canvas_resolution_controller
    )


__all__ = ["publish_input_canvas_composition"]
