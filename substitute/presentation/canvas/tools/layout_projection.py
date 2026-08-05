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

"""Resolve tool inventory and user layout into renderable toolbar slots."""

from __future__ import annotations

from dataclasses import dataclass

from .layout import CanvasToolGroupSlot, CanvasToolLayoutSnapshot
from .model import CanvasToolPresentation


@dataclass(frozen=True, slots=True)
class CanvasToolSlotPresentation:
    """Present one resolved toolbar slot and every currently available member."""

    slot_id: str
    current: CanvasToolPresentation
    members: tuple[CanvasToolPresentation, ...]

    @property
    def tool_id(self) -> str:
        """Return the tool currently presented by the slot."""

        return self.current.tool_id

    @property
    def grouped(self) -> bool:
        """Return whether the slot currently exposes multiple members."""

        return len(self.members) > 1


def resolve_canvas_tool_slots(
    presentations: tuple[CanvasToolPresentation, ...],
    layout: CanvasToolLayoutSnapshot | None,
) -> tuple[CanvasToolSlotPresentation, ...]:
    """Project available tools through optional user grouping and ordering."""

    if layout is None:
        return tuple(
            CanvasToolSlotPresentation(
                slot_id=presentation.tool_id,
                current=presentation,
                members=(presentation,),
            )
            for presentation in presentations
        )
    by_id = {presentation.tool_id: presentation for presentation in presentations}
    projected: list[CanvasToolSlotPresentation] = []
    assigned: set[str] = set()
    for slot in layout.slots:
        members = tuple(
            by_id[tool_id]
            for tool_id in slot.tool_ids
            if tool_id in by_id and tool_id not in layout.hidden_tool_ids
        )
        assigned.update(slot.tool_ids)
        if not members:
            continue
        current = _current_member(slot, members)
        projected.append(
            CanvasToolSlotPresentation(
                slot_id=slot.slot_id,
                current=current,
                members=members,
            )
        )
    for presentation in presentations:
        if (
            presentation.tool_id in assigned
            or presentation.tool_id in layout.hidden_tool_ids
        ):
            continue
        projected.append(
            CanvasToolSlotPresentation(
                slot_id=f"runtime.{presentation.tool_id}",
                current=presentation,
                members=(presentation,),
            )
        )
    return tuple(projected)


def _current_member(
    slot: CanvasToolGroupSlot,
    members: tuple[CanvasToolPresentation, ...],
) -> CanvasToolPresentation:
    """Choose the active, remembered, or first available member in that order."""

    active = next((member for member in members if member.active), None)
    if active is not None:
        return active
    selected = next(
        (member for member in members if member.tool_id == slot.selected_tool_id),
        None,
    )
    return members[0] if selected is None else selected


__all__ = ["CanvasToolSlotPresentation", "resolve_canvas_tool_slots"]
