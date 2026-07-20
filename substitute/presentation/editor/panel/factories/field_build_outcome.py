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

"""Describe production field-build outcomes without sentinel interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EditorFieldBuildKind(StrEnum):
    """Classify every production field-factory result."""

    WIDGET = "widget"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    LAYOUT_HANDLED = "layout_handled"
    INTENTIONAL_ABSENCE = "intentional_absence"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class EditorFieldBuildOutcome:
    """Carry one typed field result, diagnostic reason, and preserved error."""

    kind: EditorFieldBuildKind
    surface: object | None = None
    reason: str = ""
    error: Exception | None = None

    @property
    def rendered(self) -> bool:
        """Return whether this outcome owns a usable field surface."""

        return self.kind in {
            EditorFieldBuildKind.WIDGET,
            EditorFieldBuildKind.EMPTY,
            EditorFieldBuildKind.UNAVAILABLE,
        }


__all__ = ["EditorFieldBuildKind", "EditorFieldBuildOutcome"]
