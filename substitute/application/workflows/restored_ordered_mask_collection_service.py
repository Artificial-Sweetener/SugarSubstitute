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

"""Reconcile restored regional mask collections with authored graph values."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import InputAssetCardinality, WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.restored_ordered_mask_collection_service")


class RestoredOrderedMaskCollectionService:
    """Restore graph-list projections from durable regional collection state."""

    def __init__(
        self,
        *,
        endpoint_service: InputAssetEndpointService,
        graph_sections: WorkflowGraphSectionService,
        graph_values: OrderedMaskGraphValueService,
    ) -> None:
        """Bind graph topology and ordered graph-value owners."""

        self._endpoint_service = endpoint_service
        self._graph_sections = graph_sections
        self._graph_values = graph_values

    def reconcile(self, workflows: Mapping[str, WorkflowState]) -> int:
        """Synchronize every restored collection and return the repaired count."""

        repaired_count = 0
        for workflow_id, workflow in workflows.items():
            for association_key, collection in tuple(
                workflow.canvas.regional_mask_collections.items()
            ):
                section_key, mask_node_name = association_key
                graph = self._graph_sections.graph(workflow, section_key)
                if graph is None:
                    self._log_rejection(
                        workflow_id,
                        association_key,
                        reason="missing_graph_section",
                    )
                    continue
                endpoint_index = self._endpoint_service.build_index(
                    section_key,
                    graph,
                )
                endpoint = next(
                    (
                        candidate
                        for candidate in endpoint_index.mask_endpoints
                        if candidate.node_name == mask_node_name
                        and candidate.cardinality is InputAssetCardinality.ORDERED
                    ),
                    None,
                )
                if endpoint is None:
                    self._log_rejection(
                        workflow_id,
                        association_key,
                        reason="missing_ordered_mask_binding",
                    )
                    continue
                self._graph_values.synchronize_endpoint(
                    workflow,
                    endpoint,
                    collection,
                )
                repaired_count += 1
                log_debug(
                    _LOGGER,
                    "Reconciled restored ordered mask collection",
                    workflow_id=workflow_id,
                    section_key=section_key,
                    mask_node_name=mask_node_name,
                    region_count=len(collection.entries),
                )
        return repaired_count

    @staticmethod
    def _log_rejection(
        workflow_id: str,
        association_key: tuple[str, str],
        *,
        reason: str,
    ) -> None:
        """Log one restored collection that cannot safely project to its graph."""

        log_warning(
            _LOGGER,
            "Restored ordered mask collection could not be reconciled",
            workflow_id=workflow_id,
            section_key=association_key[0],
            mask_node_name=association_key[1],
            rejection_reason=reason,
        )


__all__ = ["RestoredOrderedMaskCollectionService"]
