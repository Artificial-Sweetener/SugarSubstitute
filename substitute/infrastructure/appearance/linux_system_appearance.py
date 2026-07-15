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

"""Provide Linux appearance through XDG portal values with Qt fallbacks."""

from __future__ import annotations

from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.domain.appearance import SystemAppearanceSnapshot
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.xdg_settings_portal import (
    XdgSettingsPortalClient,
    read_portal_accent_color,
    read_portal_color_scheme,
)


class LinuxSystemAppearanceProvider:
    """Prefer standardized portal settings and fill missing fields through Qt."""

    def __init__(
        self,
        *,
        portal_client: XdgSettingsPortalClient | None = None,
        qt_provider: QtSystemAppearanceProvider | None = None,
    ) -> None:
        """Store isolated portal and Qt appearance collaborators."""

        self._portal_client = portal_client or XdgSettingsPortalClient()
        self._qt_provider = qt_provider or QtSystemAppearanceProvider()

    def probe(self) -> SystemAppearanceProbe:
        """Return one fresh Linux appearance snapshot."""

        portal_scheme = read_portal_color_scheme(self._portal_client)
        portal_accent = read_portal_accent_color(self._portal_client)
        fallback = self._qt_provider.probe()
        color_scheme = portal_scheme or fallback.snapshot.color_scheme
        accent_color = portal_accent or fallback.snapshot.accent_color
        return SystemAppearanceProbe(
            snapshot=SystemAppearanceSnapshot(color_scheme, accent_color),
            adapter_name="linux",
            color_scheme_source=(
                "xdg_portal"
                if portal_scheme is not None
                else fallback.color_scheme_source
            ),
            accent_color_source=(
                "xdg_portal"
                if portal_accent is not None
                else fallback.accent_color_source
            ),
        )


__all__ = ["LinuxSystemAppearanceProvider"]
