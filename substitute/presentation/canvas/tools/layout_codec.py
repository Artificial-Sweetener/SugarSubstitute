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

"""Encode configurable canvas-tool layouts through one versioned schema."""

from __future__ import annotations

from collections.abc import Mapping

from .layout import CanvasToolGroupSlot, CanvasToolLayoutSnapshot

_SCHEMA_VERSION = 1


class CanvasToolLayoutCodec:
    """Translate immutable toolbar layouts to and from persistence-safe mappings."""

    def encode(self, snapshot: CanvasToolLayoutSnapshot) -> dict[str, object]:
        """Return one versioned mapping containing stable identities only."""

        return {
            "version": _SCHEMA_VERSION,
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "tool_ids": list(slot.tool_ids),
                    "selected_tool_id": slot.selected_tool_id,
                }
                for slot in snapshot.slots
            ],
            "hidden_tool_ids": sorted(snapshot.hidden_tool_ids),
        }

    def decode(self, payload: Mapping[str, object]) -> CanvasToolLayoutSnapshot:
        """Validate and restore one supported toolbar-layout mapping."""

        version = payload.get("version")
        if version != _SCHEMA_VERSION:
            raise ValueError(f"unsupported canvas tool layout version: {version!r}")
        raw_slots = payload.get("slots")
        if not isinstance(raw_slots, list):
            raise ValueError("canvas tool layout slots must be a list")
        slots = tuple(self._decode_slot(raw_slot) for raw_slot in raw_slots)
        raw_hidden = payload.get("hidden_tool_ids", [])
        if not isinstance(raw_hidden, list) or any(
            not isinstance(tool_id, str) for tool_id in raw_hidden
        ):
            raise ValueError("hidden canvas tool IDs must be a string list")
        return CanvasToolLayoutSnapshot(
            slots=slots,
            hidden_tool_ids=frozenset(raw_hidden),
        )

    @staticmethod
    def _decode_slot(raw_slot: object) -> CanvasToolGroupSlot:
        """Validate one serialized slot without accepting incidental fields."""

        if not isinstance(raw_slot, Mapping):
            raise ValueError("canvas tool layout slot must be a mapping")
        slot_id = raw_slot.get("slot_id")
        tool_ids = raw_slot.get("tool_ids")
        selected_tool_id = raw_slot.get("selected_tool_id")
        if not isinstance(slot_id, str):
            raise ValueError("canvas tool layout slot_id must be a string")
        if not isinstance(tool_ids, list) or any(
            not isinstance(tool_id, str) for tool_id in tool_ids
        ):
            raise ValueError("canvas tool layout tool_ids must be a string list")
        if not isinstance(selected_tool_id, str):
            raise ValueError("selected canvas tool ID must be a string")
        return CanvasToolGroupSlot(
            slot_id=slot_id,
            tool_ids=tuple(tool_ids),
            selected_tool_id=selected_tool_id,
        )


__all__ = ["CanvasToolLayoutCodec"]
