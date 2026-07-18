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

"""Normalize legacy and current Comfy workflow link records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class WorkflowLink:
    """Describe one directed LiteGraph connection."""

    link_id: str
    origin_id: str
    origin_slot: int
    target_id: str
    target_slot: int
    value_type: str


class WorkflowLinkIndex:
    """Index normalized workflow links by id and target interface slot."""

    def __init__(self, payload: object) -> None:
        """Normalize supported link payload shapes."""

        links = tuple(_workflow_link(item) for item in _link_items(payload))
        self._by_id = {link.link_id: link for link in links}
        self._by_target = {(link.target_id, link.target_slot): link for link in links}

    def by_id(self, link_id: object) -> WorkflowLink | None:
        """Return a link by its serialized identifier."""

        return self._by_id.get(str(link_id))

    def into_target(self, target_id: object, target_slot: int) -> WorkflowLink | None:
        """Return the link entering one target slot."""

        return self._by_target.get((str(target_id), target_slot))

    def target_slots(self, target_id: object) -> tuple[int, ...]:
        """Return sorted slots with links entering one target node."""

        normalized_id = str(target_id)
        return tuple(
            sorted(
                slot for node_id, slot in self._by_target if node_id == normalized_id
            )
        )


def _link_items(payload: object) -> tuple[object, ...]:
    """Return the iterable link records from a JSON-like payload."""

    if isinstance(payload, list | tuple):
        return tuple(payload)
    return ()


def _workflow_link(payload: object) -> WorkflowLink:
    """Normalize one object or six-item legacy link record."""

    if isinstance(payload, Mapping):
        try:
            return WorkflowLink(
                link_id=str(payload["id"]),
                origin_id=str(payload["origin_id"]),
                origin_slot=_integer(payload["origin_slot"], "origin_slot"),
                target_id=str(payload["target_id"]),
                target_slot=_integer(payload["target_slot"], "target_slot"),
                value_type=str(payload.get("type", "")),
            )
        except KeyError as error:
            raise ValueError(f"Workflow link is missing {error.args[0]!r}.") from error
    if isinstance(payload, Sequence) and not isinstance(payload, str | bytes):
        if len(payload) < 6:
            raise ValueError("Legacy workflow links must contain six values.")
        return WorkflowLink(
            link_id=str(payload[0]),
            origin_id=str(payload[1]),
            origin_slot=_integer(payload[2], "origin_slot"),
            target_id=str(payload[3]),
            target_slot=_integer(payload[4], "target_slot"),
            value_type=str(payload[5]),
        )
    raise ValueError("Workflow links must be objects or six-item arrays.")


def _integer(value: object, field_name: str) -> int:
    """Return a non-boolean integer link field."""

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Workflow link {field_name} must be an integer.")
    return value


__all__ = ["WorkflowLink", "WorkflowLinkIndex"]
