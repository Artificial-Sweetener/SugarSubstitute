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

"""Retain Output detail groups while adapting image IDs to live compositions."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from cutecanvas import CanvasInspectionGroup

from substitute.application.workflows.output_detail_inspection import (
    OutputDetailInspectionGroup,
)


class OutputInspectionGroupRegistry:
    """Own durable per-workflow detail definitions for one Output document."""

    def __init__(
        self,
        composition_id_for: Callable[[UUID], UUID | None],
    ) -> None:
        """Bind the sole application-image to composition identity resolver."""

        self._composition_id_for = composition_id_for
        self._groups_by_workflow: dict[
            str, tuple[OutputDetailInspectionGroup, ...]
        ] = {}

    def replace_workflow_groups(
        self,
        workflow_id: str,
        groups: tuple[OutputDetailInspectionGroup, ...],
    ) -> tuple[CanvasInspectionGroup, ...]:
        """Replace one workflow's definitions and return every live group."""

        candidate = self._candidate_groups(workflow_id, groups)
        live_groups = self._live_groups(candidate)
        self._groups_by_workflow = candidate
        return live_groups

    def validate_workflow_groups(
        self,
        workflow_id: str,
        groups: tuple[OutputDetailInspectionGroup, ...],
    ) -> tuple[CanvasInspectionGroup, ...]:
        """Validate one replacement without changing retained registry state."""

        return self._live_groups(self._candidate_groups(workflow_id, groups))

    def live_groups(self) -> tuple[CanvasInspectionGroup, ...]:
        """Adapt retained definitions to currently admitted compositions."""

        return self._live_groups(self._groups_by_workflow)

    def _candidate_groups(
        self,
        workflow_id: str,
        groups: tuple[OutputDetailInspectionGroup, ...],
    ) -> dict[str, tuple[OutputDetailInspectionGroup, ...]]:
        """Return a proposed registry mapping after validating group ownership."""

        if any(group.workflow_id != workflow_id for group in groups):
            raise ValueError("detail inspection group workflow does not match owner")
        candidate = dict(self._groups_by_workflow)
        if groups:
            candidate[workflow_id] = groups
        else:
            candidate.pop(workflow_id, None)
        return candidate

    def _live_groups(
        self,
        groups_by_workflow: dict[str, tuple[OutputDetailInspectionGroup, ...]],
    ) -> tuple[CanvasInspectionGroup, ...]:
        """Resolve and validate one complete proposed live group set."""

        resolved: list[CanvasInspectionGroup] = []
        group_ids: set[UUID] = set()
        assigned_compositions: set[UUID] = set()
        for groups in groups_by_workflow.values():
            for group in groups:
                composition_ids = tuple(
                    dict.fromkeys(
                        composition_id
                        for image_id in group.image_ids
                        if (composition_id := self._composition_id_for(image_id))
                        is not None
                    )
                )
                if len(composition_ids) > 1:
                    if group.group_id in group_ids:
                        raise ValueError("detail inspection group IDs must be unique")
                    if assigned_compositions.intersection(composition_ids):
                        raise ValueError(
                            "inspection targets cannot belong to multiple groups"
                        )
                    group_ids.add(group.group_id)
                    assigned_compositions.update(composition_ids)
                    resolved.append(
                        CanvasInspectionGroup(group.group_id, composition_ids)
                    )
        return tuple(resolved)

    def discard_workflow(
        self,
        workflow_id: str,
    ) -> tuple[CanvasInspectionGroup, ...]:
        """Discard one closed workflow's definitions and return live survivors."""

        candidate = dict(self._groups_by_workflow)
        candidate.pop(workflow_id, None)
        live_groups = self._live_groups(candidate)
        self._groups_by_workflow = candidate
        return live_groups

    def clear(self) -> None:
        """Release all retained workflow definitions."""

        self._groups_by_workflow.clear()


__all__ = ["OutputInspectionGroupRegistry"]
