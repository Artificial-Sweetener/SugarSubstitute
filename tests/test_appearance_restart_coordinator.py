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

"""Tests for appearance restart requirement coordination."""

from __future__ import annotations

from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController
from substitute.application.appearance import (
    ActiveAppearanceBaseline,
    AppearancePreferenceService,
    AppearanceResolver,
    AppearanceRestartCoordinator,
    WindowMaterialCapabilities,
)
from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.application.restart_requirements import (
    RestartRequirementService,
    RestartScope,
)
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearancePreferences,
    AppearanceThemeMode,
    SystemAppearanceSnapshot,
)


def test_theme_mode_change_registers_window_restart_delta() -> None:
    """Theme saves should create a GUI-scoped restart requirement."""

    coordinator, restart_requirements = _coordinator()

    snapshot = coordinator.set_theme_mode(AppearanceThemeMode.LIGHT)

    assert snapshot.count == 1
    item = snapshot.items[0]
    assert item.key == "appearance.theme_mode"
    assert item.label == "Theme mode"
    assert item.active_value == "dark"
    assert item.saved_value == "light"
    assert item.scope is RestartScope.WINDOW
    assert restart_requirements.snapshot().required_scope is RestartScope.WINDOW


def test_theme_mode_change_back_to_active_clears_restart_delta() -> None:
    """Theme saves should clear pending work when saved value matches baseline."""

    coordinator, restart_requirements = _coordinator()

    coordinator.set_theme_mode(AppearanceThemeMode.LIGHT)
    snapshot = coordinator.set_theme_mode(AppearanceThemeMode.DARK)

    assert snapshot.count == 0
    assert restart_requirements.snapshot().count == 0


def test_backdrop_mode_change_registers_window_restart_delta() -> None:
    """Backdrop saves should create a GUI-scoped restart requirement."""

    coordinator, _restart_requirements = _coordinator()

    snapshot = coordinator.set_backdrop_mode(AppearanceBackdropMode.ACRYLIC)

    assert snapshot.count == 1
    item = snapshot.items[0]
    assert item.key == "appearance.backdrop_mode"
    assert item.label == "Window material"
    assert item.active_value == "mica_alt"
    assert item.saved_value == "acrylic"
    assert item.scope is RestartScope.WINDOW


def test_record_applied_preferences_updates_baseline_and_clears_items() -> None:
    """Applied preferences should become the active baseline after GUI reload."""

    coordinator, restart_requirements = _coordinator()

    coordinator.set_theme_mode(AppearanceThemeMode.LIGHT)
    coordinator.set_backdrop_mode(AppearanceBackdropMode.ACRYLIC)
    snapshot = coordinator.record_applied_preferences()

    assert snapshot.count == 0
    assert restart_requirements.snapshot().count == 0
    assert coordinator.set_theme_mode(AppearanceThemeMode.LIGHT).count == 0
    assert coordinator.set_backdrop_mode(AppearanceBackdropMode.ACRYLIC).count == 0


def _coordinator() -> tuple[AppearanceRestartCoordinator, RestartRequirementService]:
    """Create a coordinator with dark/Mica active appearance for tests."""

    preferences = AppearancePreferences(
        schema_version="1",
        theme_mode=AppearanceThemeMode.DARK,
        accent_source=AppearanceAccentSource.CUSTOM,
        custom_accent_color="#E91E63",
        backdrop_mode=AppearanceBackdropMode.MICA_ALT,
    )
    runtime = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(
            _MemoryAppearancePreferenceRepository(preferences)
        ),
        resolver=AppearanceResolver(
            WindowMaterialCapabilities(
                acrylic_available=True,
                mica_alt_available=True,
            )
        ),
        system_appearance_provider=_FixedSystemAppearanceProvider(),
    )
    restart_requirements = RestartRequirementService()
    return (
        AppearanceRestartCoordinator(
            appearance_runtime=runtime,
            active_baseline=ActiveAppearanceBaseline(preferences),
            restart_requirements=restart_requirements,
        ),
        restart_requirements,
    )


class _FixedSystemAppearanceProvider:
    """Provide an empty deterministic appearance snapshot for coordinator tests."""

    def probe(self) -> SystemAppearanceProbe:
        """Return one fixed system appearance probe."""

        return SystemAppearanceProbe(
            snapshot=SystemAppearanceSnapshot(),
            adapter_name="test",
        )


class _MemoryAppearancePreferenceRepository:
    """Provide an in-memory appearance preference repository for tests."""

    def __init__(self, preferences: AppearancePreferences) -> None:
        """Store the preference snapshot returned by load."""

        self.preferences = preferences

    def load(self) -> AppearancePreferences:
        """Return the stored preference snapshot."""

        return self.preferences

    def save(self, preferences: AppearancePreferences) -> None:
        """Replace the stored preference snapshot."""

        self.preferences = preferences
