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

"""Resolve QFluent menu-button placement independently of click lifecycle."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QAbstractButton
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]


class MenuButtonPositioner:
    """Choose and prepare the visible popup direction for one button."""

    def __init__(
        self,
        button: QAbstractButton,
        *,
        fallback_position: Callable[[], QPoint],
        animation_type: MenuAnimationType,
        qfluent_drop_down_vertical_offset: int,
    ) -> None:
        """Store geometry providers without owning menu visibility state."""

        self._button = button
        self._fallback_position = fallback_position
        self._animation_type = animation_type
        self._qfluent_drop_down_vertical_offset = qfluent_drop_down_vertical_offset

    def resolve(self, menu: object) -> tuple[QPoint, MenuAnimationType]:
        """Return a left-anchored QFluent popup position and animation type."""

        view = getattr(menu, "view", None)
        height_for_animation = getattr(view, "heightForAnimation", None)
        if view is None or not callable(height_for_animation):
            return self._fallback_position(), self._animation_type

        self._prepare_menu_size(menu, view)
        # QFluent treats exec().x as the visible list edge and subtracts its
        # transparent layout margin when moving the popup window.
        drop_down_position = self._button.mapToGlobal(
            QPoint(
                0,
                self._button.height() + self._qfluent_drop_down_vertical_offset,
            )
        )
        pull_up_position = self._button.mapToGlobal(QPoint(0, 0))
        drop_down_height = int(
            height_for_animation(drop_down_position, MenuAnimationType.DROP_DOWN)
        )
        pull_up_height = int(
            height_for_animation(pull_up_position, MenuAnimationType.PULL_UP)
        )
        if drop_down_height >= pull_up_height:
            self._adjust_menu_view(
                view,
                drop_down_position,
                MenuAnimationType.DROP_DOWN,
            )
            return drop_down_position, MenuAnimationType.DROP_DOWN

        self._adjust_menu_view(view, pull_up_position, MenuAnimationType.PULL_UP)
        return pull_up_position, MenuAnimationType.PULL_UP

    def _prepare_menu_size(self, menu: object, view: object) -> None:
        """Apply QFluent dropdown sizing before positioning a menu."""

        set_minimum_width = getattr(view, "setMinimumWidth", None)
        if callable(set_minimum_width):
            set_minimum_width(self._button.width())
        adjust_view_size = getattr(view, "adjustSize", None)
        if callable(adjust_view_size):
            adjust_view_size()
        adjust_menu_size = getattr(menu, "adjustSize", None)
        if callable(adjust_menu_size):
            adjust_menu_size()

    @staticmethod
    def _adjust_menu_view(
        view: object,
        position: QPoint,
        animation_type: MenuAnimationType,
    ) -> None:
        """Resize the QFluent menu view for the selected popup direction."""

        adjust_size = getattr(view, "adjustSize", None)
        if not callable(adjust_size):
            return
        try:
            adjust_size(position, animation_type)
        except TypeError:
            adjust_size()


__all__ = ["MenuButtonPositioner"]
