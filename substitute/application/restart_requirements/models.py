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

"""Define process-local restart requirement state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RestartScope(IntEnum):
    """Order restart scopes by increasing runtime cost."""

    NONE = 0
    WINDOW = 1
    FULL_APP = 2


@dataclass(frozen=True, slots=True)
class RestartRequirementItem:
    """Describe one saved setting whose value is pending restart application."""

    key: str
    label: str
    active_value: str
    saved_value: str
    scope: RestartScope
    detail: str | None = None

    def __post_init__(self) -> None:
        """Validate invariant fields for a pending restart delta."""

        if not self.key.strip():
            raise ValueError("Restart requirement key cannot be blank.")
        if not self.label.strip():
            raise ValueError("Restart requirement label cannot be blank.")
        if self.scope is RestartScope.NONE:
            raise ValueError("Pending restart requirement scope cannot be NONE.")


@dataclass(frozen=True, slots=True)
class RestartRequirementSnapshot:
    """Capture the current restart cart contents and most expensive scope."""

    items: tuple[RestartRequirementItem, ...]
    required_scope: RestartScope

    @property
    def count(self) -> int:
        """Return the number of pending restart items."""

        return len(self.items)
