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

"""Read standardized Linux appearance settings from the XDG desktop portal."""

from __future__ import annotations

import math
from numbers import Real

from PySide6.QtDBus import (
    QDBus,
    QDBusArgument,
    QDBusConnection,
    QDBusMessage,
    QDBusVariant,
)

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("infrastructure.appearance.xdg_portal")
_PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_SETTINGS_INTERFACE = "org.freedesktop.portal.Settings"
_APPEARANCE_NAMESPACE = "org.freedesktop.appearance"


class XdgSettingsPortalClient:
    """Perform bounded synchronous reads against the desktop settings portal."""

    def __init__(self, timeout_ms: int = 500) -> None:
        """Store the maximum time allowed for each portal request."""

        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self._timeout_ms = timeout_ms

    def read_one(self, namespace: str, key: str) -> object | None:
        """Return one unwrapped portal value or None when unavailable."""

        connection = QDBusConnection.sessionBus()
        if not connection.isConnected():
            log_debug(_LOGGER, "XDG settings portal session bus is unavailable")
            return None
        message = QDBusMessage.createMethodCall(
            _PORTAL_SERVICE,
            _PORTAL_PATH,
            _SETTINGS_INTERFACE,
            "ReadOne",
        )
        message.setArguments([namespace, key])
        reply = connection.call(message, QDBus.CallMode.Block, self._timeout_ms)
        if reply.type() is not QDBusMessage.MessageType.ReplyMessage:
            log_debug(
                _LOGGER,
                "XDG settings portal read failed",
                namespace=namespace,
                setting=key,
                dbus_error=reply.errorName(),
            )
            return None
        arguments = reply.arguments()
        if len(arguments) != 1:
            log_debug(
                _LOGGER,
                "XDG settings portal returned an unexpected argument count",
                namespace=namespace,
                setting=key,
                argument_count=len(arguments),
            )
            return None
        return _unwrap_dbus_value(arguments[0])


def read_portal_color_scheme(
    client: XdgSettingsPortalClient,
) -> SystemColorScheme | None:
    """Decode the standardized XDG color-scheme preference."""

    raw_value = client.read_one(_APPEARANCE_NAMESPACE, "color-scheme")
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        return None
    if raw_value == 1:
        return SystemColorScheme.DARK
    if raw_value == 2:
        return SystemColorScheme.LIGHT
    return None


def read_portal_accent_color(client: XdgSettingsPortalClient) -> RgbColor | None:
    """Decode the standardized XDG sRGB tuple as byte channels."""

    raw_value = client.read_one(_APPEARANCE_NAMESPACE, "accent-color")
    if not isinstance(raw_value, (list, tuple)) or len(raw_value) != 3:
        return None
    channels: list[int] = []
    for raw_channel in raw_value:
        if isinstance(raw_channel, bool) or not isinstance(raw_channel, Real):
            return None
        channel = float(raw_channel)
        if not math.isfinite(channel) or channel < 0.0 or channel > 1.0:
            return None
        channels.append(round(channel * 255))
    return RgbColor(*channels)


def _unwrap_dbus_value(value: object) -> object:
    """Unwrap the variant containers PySide may return for portal values."""

    current = value
    for _depth in range(4):
        if isinstance(current, QDBusVariant):
            current = current.variant()
            continue
        if isinstance(current, QDBusArgument):
            current = current.asVariant()
            continue
        break
    return current


__all__ = [
    "XdgSettingsPortalClient",
    "read_portal_accent_color",
    "read_portal_color_scheme",
]
