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

"""Own restart presentation controllers and native widgets exactly."""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtWidgets import QWidget

from substitute.presentation.restart_requirements import RestartRequirementUiController
from tests.support.qt.lifecycle import destroy_qt_object


_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class RestartPresentationOwner:
    """Own one test's controller subscriptions and independent widget roots."""

    def __init__(self) -> None:
        """Initialize empty controller and widget ownership."""

        self._controllers: list[RestartRequirementUiController] = []
        self._widgets: list[QWidget] = []

    def own_widget(self, widget: _WidgetT) -> _WidgetT:
        """Retain one independently constructed widget root."""

        self._widgets.append(widget)
        return widget

    def own_controller(
        self,
        controller: RestartRequirementUiController,
    ) -> RestartRequirementUiController:
        """Retain one service and button subscription owner."""

        self._controllers.append(controller)
        return controller

    def destroy_all(self) -> None:
        """Disconnect controllers before synchronously destroying widgets."""

        for controller in reversed(self._controllers):
            controller.dispose()
        self._controllers.clear()
        for widget in reversed(self._widgets):
            destroy_qt_object(widget)
        self._widgets.clear()


__all__ = ["RestartPresentationOwner"]
