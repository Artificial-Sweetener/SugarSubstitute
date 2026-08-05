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

"""Own configurable canvas-toolbar grouping independently from tool inventory."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from weakref import ReferenceType, ref


@dataclass(frozen=True, slots=True)
class CanvasToolGroupSlot:
    """Describe one ordered toolbar slot containing one or more tool identities."""

    slot_id: str
    tool_ids: tuple[str, ...]
    selected_tool_id: str

    def __post_init__(self) -> None:
        """Reject unstable identities and ambiguous group membership."""

        if not self.slot_id or self.slot_id != self.slot_id.strip():
            raise ValueError("canvas tool slot_id must be a non-blank stable ID")
        if not self.tool_ids or any(
            not tool_id or tool_id != tool_id.strip() for tool_id in self.tool_ids
        ):
            raise ValueError("canvas tool group must contain stable tool IDs")
        if len(set(self.tool_ids)) != len(self.tool_ids):
            raise ValueError("canvas tool group must not contain duplicate tools")
        if self.selected_tool_id not in self.tool_ids:
            raise ValueError("selected canvas tool must belong to its group")


@dataclass(frozen=True, slots=True)
class CanvasToolLayoutSnapshot:
    """Capture the complete durable ordering and grouping of one tool strip."""

    slots: tuple[CanvasToolGroupSlot, ...]
    hidden_tool_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Reject duplicate slots, duplicate membership, and invalid hidden IDs."""

        slot_ids = tuple(slot.slot_id for slot in self.slots)
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("canvas tool layout must not contain duplicate slots")
        tool_ids = tuple(tool_id for slot in self.slots for tool_id in slot.tool_ids)
        if len(set(tool_ids)) != len(tool_ids):
            raise ValueError("canvas tool layout must not place a tool more than once")
        if any(
            not tool_id or tool_id != tool_id.strip()
            for tool_id in self.hidden_tool_ids
        ):
            raise ValueError("hidden canvas tool IDs must be stable identities")


CanvasToolLayoutListener = Callable[[CanvasToolLayoutSnapshot], None]


class CanvasToolLayoutSubscription:
    """Own one removable layout listener without retaining the layout."""

    def __init__(self, layout: CanvasToolLayout, listener_id: int) -> None:
        """Store a weak layout reference and opaque listener identity."""

        self._layout_ref: ReferenceType[CanvasToolLayout] = ref(layout)
        self._listener_id: int | None = listener_id

    def close(self) -> None:
        """Remove the listener idempotently."""

        listener_id = self._listener_id
        if listener_id is None:
            return
        self._listener_id = None
        layout = self._layout_ref()
        if layout is not None:
            layout._unsubscribe(listener_id)


class CanvasToolLayout:
    """Own toolbar arrangement and remembered group representatives."""

    def __init__(self, snapshot: CanvasToolLayoutSnapshot) -> None:
        """Initialize one validated layout and its listener catalog."""

        self._snapshot = snapshot
        self._listeners: dict[int, CanvasToolLayoutListener] = {}
        self._next_listener_id = 1

    def snapshot(self) -> CanvasToolLayoutSnapshot:
        """Return the current immutable layout."""

        return self._snapshot

    def replace(self, snapshot: CanvasToolLayoutSnapshot) -> None:
        """Replace the complete layout and publish one atomic change."""

        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self._notify()

    def select_group_tool(self, slot_id: str, tool_id: str) -> bool:
        """Remember one member as the representative of its containing slot."""

        slots = list(self._snapshot.slots)
        for index, slot in enumerate(slots):
            if slot.slot_id != slot_id:
                continue
            if tool_id not in slot.tool_ids:
                return False
            if slot.selected_tool_id == tool_id:
                return True
            slots[index] = replace(slot, selected_tool_id=tool_id)
            self.replace(replace(self._snapshot, slots=tuple(slots)))
            return True
        return False

    def remember_tool(self, tool_id: str | None) -> bool:
        """Remember an activated member without changing slot order or membership."""

        if tool_id is None:
            return False
        for slot in self._snapshot.slots:
            if tool_id in slot.tool_ids:
                return self.select_group_tool(slot.slot_id, tool_id)
        return False

    def move_slot(self, slot_id: str, destination_index: int) -> bool:
        """Move one slot to a clamped index for future customization surfaces."""

        slots = list(self._snapshot.slots)
        source_index = next(
            (index for index, slot in enumerate(slots) if slot.slot_id == slot_id),
            None,
        )
        if source_index is None:
            return False
        slot = slots.pop(source_index)
        destination_index = max(0, min(int(destination_index), len(slots)))
        slots.insert(destination_index, slot)
        self.replace(replace(self._snapshot, slots=tuple(slots)))
        return True

    def move_tool(
        self,
        tool_id: str,
        destination_slot_id: str,
        destination_index: int,
    ) -> bool:
        """Move one tool between groups while retaining valid representatives."""

        slots = list(self._snapshot.slots)
        source_index = next(
            (index for index, slot in enumerate(slots) if tool_id in slot.tool_ids),
            None,
        )
        destination_index_in_layout = next(
            (
                index
                for index, slot in enumerate(slots)
                if slot.slot_id == destination_slot_id
            ),
            None,
        )
        if source_index is None or destination_index_in_layout is None:
            return False
        source = slots[source_index]
        if source.slot_id == destination_slot_id:
            members = list(source.tool_ids)
            members.remove(tool_id)
            destination_index = max(0, min(int(destination_index), len(members)))
            members.insert(destination_index, tool_id)
            slots[source_index] = replace(source, tool_ids=tuple(members))
            self.replace(replace(self._snapshot, slots=tuple(slots)))
            return True
        remaining = tuple(member for member in source.tool_ids if member != tool_id)
        if remaining:
            slots[source_index] = replace(
                source,
                tool_ids=remaining,
                selected_tool_id=(
                    remaining[0]
                    if source.selected_tool_id == tool_id
                    else source.selected_tool_id
                ),
            )
        else:
            slots.pop(source_index)
        destination_position = next(
            index
            for index, slot in enumerate(slots)
            if slot.slot_id == destination_slot_id
        )
        destination = slots[destination_position]
        members = list(destination.tool_ids)
        destination_index = max(0, min(int(destination_index), len(members)))
        members.insert(destination_index, tool_id)
        slots[destination_position] = replace(destination, tool_ids=tuple(members))
        self.replace(replace(self._snapshot, slots=tuple(slots)))
        return True

    def set_tool_hidden(self, tool_id: str, hidden: bool) -> bool:
        """Update durable visibility without removing grouping information."""

        hidden_tool_ids = set(self._snapshot.hidden_tool_ids)
        before = tool_id in hidden_tool_ids
        if hidden:
            hidden_tool_ids.add(tool_id)
        else:
            hidden_tool_ids.discard(tool_id)
        if before == hidden:
            return False
        self.replace(
            replace(self._snapshot, hidden_tool_ids=frozenset(hidden_tool_ids))
        )
        return True

    def subscribe(
        self,
        listener: CanvasToolLayoutListener,
    ) -> CanvasToolLayoutSubscription:
        """Observe future layout changes through an owned subscription."""

        listener_id = self._next_listener_id
        self._next_listener_id += 1
        self._listeners[listener_id] = listener
        return CanvasToolLayoutSubscription(self, listener_id)

    def _unsubscribe(self, listener_id: int) -> None:
        """Remove one opaque listener identity."""

        self._listeners.pop(listener_id, None)

    def _notify(self) -> None:
        """Publish the immutable layout safely across reentrant mutations."""

        snapshot = self._snapshot
        for listener in tuple(self._listeners.values()):
            listener(snapshot)


def create_canvas_tool_layout(
    slots: Iterable[CanvasToolGroupSlot],
) -> CanvasToolLayout:
    """Create a mutable layout from one ordered built-in slot catalog."""

    return CanvasToolLayout(CanvasToolLayoutSnapshot(tuple(slots)))


__all__ = [
    "CanvasToolGroupSlot",
    "CanvasToolLayout",
    "CanvasToolLayoutListener",
    "CanvasToolLayoutSnapshot",
    "CanvasToolLayoutSubscription",
    "create_canvas_tool_layout",
]
