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

"""Define field-owned semantic actions that may appear in a node menu."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QPoint
from substitute.presentation.widgets.menu_model import MenuEntry


@dataclass(frozen=True, slots=True)
class FieldActionContext:
    """Describe the node-menu invocation without defining field semantics."""

    anchor_global_position: QPoint


@dataclass(frozen=True, slots=True)
class FieldActionContribution:
    """Provide one dynamically evaluated field-action contribution."""

    contribution_id: str
    availability_factory: Callable[[], bool]
    entries_factory: Callable[[FieldActionContext], tuple[MenuEntry, ...]]

    def is_available(self) -> bool:
        """Return whether this contribution currently exposes any valid action."""

        return self.availability_factory()

    def entries(self, context: FieldActionContext) -> tuple[MenuEntry, ...]:
        """Return actions reflecting the field's current live state."""

        return self.entries_factory(context)


@runtime_checkable
class FieldActionSource(Protocol):
    """Expose semantic field actions without exposing local editor commands."""

    def field_actions_available(self) -> bool:
        """Return whether the field currently exposes semantic actions."""

    def field_action_entries(
        self,
        context: FieldActionContext,
    ) -> tuple[MenuEntry, ...]:
        """Return current semantic actions for an aggregate node menu."""


__all__ = ["FieldActionContext", "FieldActionContribution", "FieldActionSource"]
