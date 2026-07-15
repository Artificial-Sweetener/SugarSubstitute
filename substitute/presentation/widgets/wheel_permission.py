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

"""Provide optional wheel-event permission hooks for reusable widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias, cast

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

WHEEL_INTENT_PERMISSION_ATTRIBUTE = "_wheel_intent_permission"
WheelIntentPermission: TypeAlias = Callable[[QWidget, QWheelEvent], bool]


def wheel_event_is_allowed(widget: QWidget, event: QWheelEvent) -> bool:
    """Return whether a widget may consume one wheel event."""

    permission = getattr(widget, WHEEL_INTENT_PERMISSION_ATTRIBUTE, None)
    if permission is None:
        return True
    if not callable(permission):
        return True
    return bool(cast(WheelIntentPermission, permission)(widget, event))


def set_wheel_intent_permission(
    widget: QWidget,
    permission: WheelIntentPermission,
) -> None:
    """Attach a wheel permission callback to one widget."""

    setattr(widget, WHEEL_INTENT_PERMISSION_ATTRIBUTE, permission)


__all__ = [
    "WHEEL_INTENT_PERMISSION_ATTRIBUTE",
    "WheelIntentPermission",
    "set_wheel_intent_permission",
    "wheel_event_is_allowed",
]
