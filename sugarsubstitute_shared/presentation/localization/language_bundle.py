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

"""Define the preloaded active-only bundle exchanged by locale transactions."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QFont
from PySide6.QtCore import QTranslator

from sugarsubstitute_shared.localization import ResolvedLocale


class PreparedLanguageBundle:
    """Retain one complete candidate generation until activation or disposal."""

    def __init__(
        self,
        *,
        resolved_locale: ResolvedLocale,
        translators: tuple[QTranslator, ...],
        application_font: QFont,
        payload: object | None = None,
        release_callback: Callable[[], None] | None = None,
    ) -> None:
        """Store resources that were fully loaded before visible state changes."""

        self._resolved_locale = resolved_locale
        self._translators = translators
        self._application_font = QFont(application_font)
        self._payload = payload
        self._release_callback = release_callback
        self._released = False

    @property
    def resolved_locale(self) -> ResolvedLocale:
        """Return the preference and effective locale used to prepare the bundle."""

        return self._resolved_locale

    @property
    def translators(self) -> tuple[QTranslator, ...]:
        """Return active delegates in app-to-Qt fallback priority order."""

        return self._translators

    @property
    def application_font(self) -> QFont:
        """Return a copy of the active locale-specific application font."""

        return QFont(self._application_font)

    @property
    def payload(self) -> object | None:
        """Return an immutable app-owned snapshot prepared with this generation."""

        return self._payload

    @property
    def released(self) -> bool:
        """Return whether this detached generation has released owned resources."""

        return self._released

    def release(self) -> None:
        """Release fonts or external resources once after the generation detaches."""

        if self._released:
            return
        self._released = True
        if self._release_callback is not None:
            self._release_callback()


__all__ = ["PreparedLanguageBundle"]
