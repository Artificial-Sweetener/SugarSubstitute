#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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

        if any(group.workflow_id != workflow_id for group in groups):
            raise ValueError("detail inspection group workflow does not match owner")
        if groups:
            self._groups_by_workflow[workflow_id] = groups
        else:
            self._groups_by_workflow.pop(workflow_id, None)
        return self.live_groups()

    def live_groups(self) -> tuple[CanvasInspectionGroup, ...]:
        """Adapt retained definitions to currently admitted compositions."""

        resolved: list[CanvasInspectionGroup] = []
        for groups in self._groups_by_workflow.values():
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
                    resolved.append(
                        CanvasInspectionGroup(group.group_id, composition_ids)
                    )
        return tuple(resolved)

    def clear(self) -> None:
        """Release all retained workflow definitions."""

        self._groups_by_workflow.clear()


__all__ = ["OutputInspectionGroupRegistry"]
