#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Associate exact generation image products with copied workflow graphs."""

from __future__ import annotations

from pathlib import Path

from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import WorkflowState


class GenerationInputImageAssociationService:
    """Resolve authored image fields and associate execution-only project assets."""

    def __init__(
        self,
        *,
        input_canvas_plan_service: InputCanvasPlanService,
        graph_section_service: WorkflowGraphSectionService,
        workflow_asset_service: WorkflowAssetService,
    ) -> None:
        """Bind graph planning and typed workflow-asset mutation owners."""
        self._plans = input_canvas_plan_service
        self._graphs = graph_section_service
        self._assets = workflow_asset_service

    def associate_project_input_image(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one exact image product through its discovered graph field."""
        graph = self._graphs.graph(workflow, section_key)
        if graph is None:
            return False
        endpoint = self._plans.build_plan(
            section_key,
            graph,
        ).image_endpoint_for_node(node_name)
        if endpoint is None:
            return False
        return self._assets.associate_project_input_image(
            workflow,
            section_key=section_key,
            node_name=node_name,
            field_key=endpoint.field_key,
            relative_path=relative_path,
        )


__all__ = ["GenerationInputImageAssociationService"]
