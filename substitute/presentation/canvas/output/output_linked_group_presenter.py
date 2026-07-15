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

"""Present Output QPane linked groups for workflow-owned final images."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid4

from qpane import LinkedGroup


class OutputLinkedGroupPane(Protocol):
    """Describe the QPane linked-group API used by Output presentation."""

    def setLinkedGroups(self, linked_groups: tuple[object, ...]) -> None:  # noqa: N802
        """Apply QPane linked-group configuration."""


class OutputLinkedGroupPresenter:
    """Apply Output linked-group display state without workflow policy ownership."""

    def __init__(self, pane: OutputLinkedGroupPane) -> None:
        """Store the Output pane that renders linked groups."""

        self._pane = pane

    def present_linked_outputs(self, output_image_ids: tuple[UUID, ...]) -> None:
        """Create a linked group only for two or more unique output images."""

        members = _linked_output_members(output_image_ids)
        linked_groups: tuple[object, ...]
        if members:
            linked_groups = (LinkedGroup(group_id=uuid4(), members=members),)
        else:
            linked_groups = ()
        self._pane.setLinkedGroups(linked_groups)


def _linked_output_members(output_image_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
    """Return linked-group members only when a workflow has two unique outputs."""

    deduplicated_members = tuple(dict.fromkeys(output_image_ids))
    if len(deduplicated_members) < 2:
        return ()
    return deduplicated_members


__all__ = ["OutputLinkedGroupPane", "OutputLinkedGroupPresenter"]
