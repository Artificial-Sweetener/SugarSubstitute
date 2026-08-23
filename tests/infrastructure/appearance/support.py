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

"""Provide deterministic readers for host appearance adapter tests."""

from __future__ import annotations

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceReader,
)
from substitute.infrastructure.appearance.xdg_settings_portal import (
    XdgSettingsPortalClient,
)


class StubQtAppearanceReader(QtSystemAppearanceReader):
    """Return deterministic normalized Qt appearance values."""

    def __init__(
        self,
        color_scheme: SystemColorScheme | None,
        accent_color: RgbColor | None,
    ) -> None:
        """Store values returned by reader methods."""

        self._color_scheme = color_scheme
        self._accent_color = accent_color

    def read_color_scheme(self) -> tuple[SystemColorScheme | None, str | None]:
        """Return the configured color scheme and deterministic source."""

        return self._color_scheme, (
            "qt_style_hints" if self._color_scheme is not None else None
        )

    def read_accent_color(self) -> RgbColor | None:
        """Return the configured accent color."""

        return self._accent_color


class StubPortalClient(XdgSettingsPortalClient):
    """Return deterministic portal payloads without a D-Bus session."""

    def __init__(self, values: dict[tuple[str, str], object]) -> None:
        """Store values keyed by portal namespace and setting."""

        super().__init__()
        self._values = values

    def read_one(self, namespace: str, key: str) -> object | None:
        """Return the configured portal value."""

        return self._values.get((namespace, key))


__all__ = ["StubPortalClient", "StubQtAppearanceReader"]
