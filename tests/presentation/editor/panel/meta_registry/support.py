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

"""Provide widget doubles shared by focused MetaRegistry contract tests."""

from __future__ import annotations


class ParentWidgetDouble:
    """Expose the layout accessor consumed by MetaRegistry widget refreshes."""

    def __init__(self, layout_obj: object) -> None:
        """Store the layout object returned to the registry."""

        self._layout_obj = layout_obj

    def layout(self) -> object:
        """Return the configured layout object."""

        return self._layout_obj


class ComboDouble:
    """Expose the parent lifecycle APIs consumed by MetaRegistry."""

    def __init__(
        self,
        parent_obj: object | None,
        parent_widget_obj: ParentWidgetDouble | None,
        valid: bool = True,
    ) -> None:
        """Initialize one independently controlled widget reference."""

        self._parent_obj = parent_obj
        self._parent_widget_obj = parent_widget_obj
        self.valid = valid
        self.parents: list[object | None] = []
        self.deleted = False

    def parent(self) -> object | None:
        """Return the configured Qt parent equivalent."""

        return self._parent_obj

    def parentWidget(self) -> ParentWidgetDouble | None:
        """Return the configured parent-widget equivalent."""

        return self._parent_widget_obj

    def setParent(self, parent: object | None) -> None:
        """Record a detach or parent transition."""

        self.parents.append(parent)
        self._parent_obj = parent

    def deleteLater(self) -> None:
        """Record deferred Qt deletion."""

        self.deleted = True
