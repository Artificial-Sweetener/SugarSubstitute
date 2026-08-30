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

"""Provide deterministic collaborators for appearance application tests."""

from __future__ import annotations

from substitute.application.appearance import (
    AppearancePreferenceService,
    AppearanceResolver,
    WindowMaterialCapabilities,
)
from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearancePreferences,
    AppearanceThemeMode,
    SystemAppearanceSnapshot,
)


class MemoryAppearancePreferenceRepository:
    """Retain appearance preferences in memory behind the repository port."""

    def __init__(self, preferences: AppearancePreferences) -> None:
        """Store the initial preference snapshot."""

        self.preferences = preferences

    def load(self) -> AppearancePreferences:
        """Return the stored preference snapshot."""

        return self.preferences

    def save(self, preferences: AppearancePreferences) -> None:
        """Replace the stored preference snapshot."""

        self.preferences = preferences


class FixedSystemAppearanceProvider:
    """Return a mutable deterministic appearance snapshot and count probes."""

    def __init__(self, snapshot: SystemAppearanceSnapshot | None = None) -> None:
        """Store the snapshot returned by each probe."""

        self.snapshot = snapshot or SystemAppearanceSnapshot()
        self.probe_count = 0

    def probe(self) -> SystemAppearanceProbe:
        """Return the configured appearance snapshot and count the probe."""

        self.probe_count += 1
        return SystemAppearanceProbe(
            snapshot=self.snapshot,
            adapter_name="test",
            color_scheme_source="test",
            accent_color_source="test",
        )


def appearance_preferences(
    *,
    theme_mode: AppearanceThemeMode = AppearanceThemeMode.DARK,
    accent_source: AppearanceAccentSource = AppearanceAccentSource.CUSTOM,
    custom_accent_color: str = "#112233",
    backdrop_mode: AppearanceBackdropMode = AppearanceBackdropMode.MICA_ALT,
) -> AppearancePreferences:
    """Build one focused normalized appearance preference snapshot."""

    return AppearancePreferences(
        schema_version="1",
        theme_mode=theme_mode,
        accent_source=accent_source,
        custom_accent_color=custom_accent_color,
        backdrop_mode=backdrop_mode,
    )


def appearance_runtime(
    *,
    preferences: AppearancePreferences | None = None,
    provider: FixedSystemAppearanceProvider | None = None,
) -> AppearanceRuntimeController:
    """Build runtime orchestration with deterministic repository and probe ports."""

    repository = MemoryAppearancePreferenceRepository(
        preferences if preferences is not None else appearance_preferences()
    )
    return AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(repository),
        resolver=AppearanceResolver(
            WindowMaterialCapabilities(
                acrylic_available=True,
                mica_alt_available=True,
            )
        ),
        system_appearance_provider=(
            provider if provider is not None else FixedSystemAppearanceProvider()
        ),
    )


__all__ = [
    "FixedSystemAppearanceProvider",
    "MemoryAppearancePreferenceRepository",
    "appearance_preferences",
    "appearance_runtime",
]
