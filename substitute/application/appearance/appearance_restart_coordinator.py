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

"""Coordinate appearance settings that require a GUI restart to apply."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

from typing import Protocol

from substitute.application.appearance.active_appearance_baseline import (
    ActiveAppearanceBaseline,
)
from substitute.application.appearance.appearance_resolver import ResolvedAppearance
from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.domain.appearance import (
    AppearanceBackdropMode,
    AppearancePreferences,
    AppearanceThemeMode,
)

THEME_MODE_RESTART_KEY = "appearance.theme_mode"
BACKDROP_MODE_RESTART_KEY = "appearance.backdrop_mode"


class AppearanceRestartRuntime(Protocol):
    """Describe runtime preference operations used by the restart coordinator."""

    def load_preferences(self) -> AppearancePreferences:
        """Load the current persisted appearance preferences."""

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> ResolvedAppearance:
        """Persist one requested theme mode without applying it live."""

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> ResolvedAppearance:
        """Persist one requested backdrop mode without applying it live."""


class AppearanceRestartCoordinator:
    """Own restart deltas for appearance settings that apply on GUI reload."""

    def __init__(
        self,
        *,
        appearance_runtime: AppearanceRestartRuntime,
        active_baseline: ActiveAppearanceBaseline,
        restart_requirements: RestartRequirementService,
    ) -> None:
        """Store collaborators for persisted appearance restart comparison."""

        self._appearance_runtime = appearance_runtime
        self._active_baseline = active_baseline
        self._restart_requirements = restart_requirements

    def set_theme_mode(
        self,
        theme_mode: AppearanceThemeMode,
    ) -> RestartRequirementSnapshot:
        """Persist theme mode and register the GUI restart delta if needed."""

        resolved = self._appearance_runtime.set_theme_mode(theme_mode)
        active = self._active_baseline.snapshot()
        return self._restart_requirements.register_delta(
            key=THEME_MODE_RESTART_KEY,
            label=app_text("Theme mode"),
            active_value=active.theme_mode.value,
            saved_value=resolved.requested.theme_mode.value,
            scope=RestartScope.WINDOW,
            detail="Substitute will apply the selected theme after the GUI restarts.",
        )

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> RestartRequirementSnapshot:
        """Persist backdrop mode and register the GUI restart delta if needed."""

        resolved = self._appearance_runtime.set_backdrop_mode(backdrop_mode)
        active = self._active_baseline.snapshot()
        return self._restart_requirements.register_delta(
            key=BACKDROP_MODE_RESTART_KEY,
            label=app_text("Window material"),
            active_value=active.backdrop_mode.value,
            saved_value=resolved.requested.backdrop_mode.value,
            scope=RestartScope.WINDOW,
            detail=(
                "Substitute will apply the selected window material after the GUI "
                "restarts."
            ),
        )

    def record_applied_preferences(self) -> RestartRequirementSnapshot:
        """Update the active baseline and clear resolved appearance deltas."""

        preferences = self._appearance_runtime.load_preferences()
        self._active_baseline.record_applied_preferences(preferences)
        self._restart_requirements.clear(THEME_MODE_RESTART_KEY)
        return self._restart_requirements.clear(BACKDROP_MODE_RESTART_KEY)


__all__ = [
    "AppearanceRestartCoordinator",
    "BACKDROP_MODE_RESTART_KEY",
    "THEME_MODE_RESTART_KEY",
]
