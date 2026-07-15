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

"""Track the appearance settings active in the current GUI shell."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.appearance import (
    AppearanceBackdropMode,
    AppearancePreferences,
    AppearanceThemeMode,
)


@dataclass(frozen=True, slots=True)
class ActiveAppearanceSnapshot:
    """Capture the restart-relevant appearance values active in the GUI."""

    theme_mode: AppearanceThemeMode
    backdrop_mode: AppearanceBackdropMode


class ActiveAppearanceBaseline:
    """Own the process-local baseline for GUI-applied appearance settings."""

    def __init__(self, preferences: AppearancePreferences) -> None:
        """Initialize the baseline from one already-applied preference snapshot."""

        self._snapshot = ActiveAppearanceSnapshot(
            theme_mode=preferences.theme_mode,
            backdrop_mode=preferences.backdrop_mode,
        )

    def snapshot(self) -> ActiveAppearanceSnapshot:
        """Return the currently active restart-relevant appearance snapshot."""

        return self._snapshot

    def record_applied_preferences(
        self,
        preferences: AppearancePreferences,
    ) -> ActiveAppearanceSnapshot:
        """Record preferences after startup or GUI reload has applied them."""

        self._snapshot = ActiveAppearanceSnapshot(
            theme_mode=preferences.theme_mode,
            backdrop_mode=preferences.backdrop_mode,
        )
        return self._snapshot


__all__ = ["ActiveAppearanceBaseline", "ActiveAppearanceSnapshot"]
