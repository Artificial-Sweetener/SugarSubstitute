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

"""Define editor projection ports shared by coordinator collaborators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class WidgetProtocol(Protocol):
    """Describe the widget methods used during editor refreshes."""

    def setParent(self, parent: object | None) -> None:
        """Detach the widget from its current parent."""

    def deleteLater(self) -> None:
        """Schedule the widget for Qt-owned deletion."""


class CubeSectionSessionWidgetProtocol(WidgetProtocol, Protocol):
    """Describe cube-section widget methods used by build sessions."""

    def defer_update_cube_height(self) -> None:
        """Schedule a cube-section height refresh."""

    def defer_string_line_edit_width_group_sync(self) -> None:
        """Schedule a cube-section string-width sync."""


class LayoutItemProtocol(Protocol):
    """Describe layout-item access used during reattachment."""

    def widget(self) -> object | None:
        """Return the contained widget when present."""

    def spacerItem(self) -> object | None:
        """Return the spacer marker when present."""

    def layout(self) -> object | None:
        """Return the nested layout when present."""


class LayoutProtocol(Protocol):
    """Describe the layout surface used by the refresh coordinator."""

    def count(self) -> int:
        """Return number of items currently tracked by the layout."""

    def takeAt(self, index: int) -> LayoutItemProtocol:
        """Remove and return one layout item."""

    def itemAt(self, index: int) -> LayoutItemProtocol:
        """Return one layout item without removing it."""

    def addSpacing(self, spacing: int) -> None:
        """Append one spacing item to the layout."""

    def addWidget(self, widget: object) -> None:
        """Append one widget to the layout."""


class SignalProtocol(Protocol):
    """Describe the signal methods used by the scroll tracking refresh."""

    def connect(self, callback: Callable[[int], None]) -> None:
        """Connect one callback."""

    def disconnect(self, callback: Callable[[int], None]) -> None:
        """Disconnect one callback."""


class ScrollBarProtocol(Protocol):
    """Describe the vertical-scrollbar surface used by the coordinator."""

    valueChanged: SignalProtocol

    def value(self) -> int:
        """Return the current scrollbar value."""


class ScrollAreaProtocol(Protocol):
    """Describe the scroll-area access used by the coordinator."""

    def verticalScrollBar(self) -> ScrollBarProtocol:
        """Return the live vertical scrollbar."""


class ProjectionCoordinatorPanelPort(Protocol):
    """Describe prior workflow state needed to create projection requests."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
