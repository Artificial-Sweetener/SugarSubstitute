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

"""Tests for runtime appearance application during startup and live updates."""

from __future__ import annotations

import sys
import types

from PySide6.QtGui import QColor
import pytest

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
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    RgbColor,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)


def test_runtime_controller_applies_persisted_auto_theme_and_system_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply resolved appearance preferences to QFluent during startup."""

    calls: list[tuple[str, object]] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda value: calls.append(("theme", value)))
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(
            _MemoryAppearancePreferenceRepository(
                AppearancePreferences(
                    schema_version="1",
                    theme_mode=AppearanceThemeMode.AUTO,
                    accent_source=AppearanceAccentSource.SYSTEM,
                    custom_accent_color="#112233",
                    backdrop_mode=AppearanceBackdropMode.MICA_ALT,
                )
            )
        ),
        resolver=_windows_resolver(),
        system_appearance_provider=_FixedSystemAppearanceProvider(
            SystemAppearanceSnapshot(
                color_scheme=SystemColorScheme.LIGHT,
                accent_color=RgbColor.from_hex("#445566"),
            )
        ),
    )

    resolved = controller.apply_persisted_preferences()

    assert resolved.effective_theme_mode is AppearanceThemeMode.LIGHT
    assert resolved.effective_accent_color == "#445566"
    assert calls == [
        ("theme", "light"),
        ("accent", QColor("#445566")),
    ]


def test_theme_mode_save_does_not_apply_qfluent_theme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving a theme mode should wait for GUI reload before applying it."""

    calls: list[tuple[str, object]] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda value: calls.append(("theme", value)))
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    repository = _MemoryAppearancePreferenceRepository(
        AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color="#112233",
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )
    )
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(repository),
        resolver=_windows_resolver(),
        system_appearance_provider=_FixedSystemAppearanceProvider(),
    )

    resolved = controller.set_theme_mode(AppearanceThemeMode.LIGHT)

    assert resolved.requested.theme_mode is AppearanceThemeMode.LIGHT
    assert calls == []


def test_accent_save_does_not_apply_pending_theme_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving accent settings should not drag a pending theme into the live UI."""

    calls: list[tuple[str, object]] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda value: calls.append(("theme", value)))
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    repository = _MemoryAppearancePreferenceRepository(
        AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color="#112233",
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )
    )
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(repository),
        resolver=_windows_resolver(),
        system_appearance_provider=_FixedSystemAppearanceProvider(),
    )

    controller.set_theme_mode(AppearanceThemeMode.LIGHT)
    resolved = controller.set_custom_accent_color("#778899")

    assert resolved.requested.theme_mode is AppearanceThemeMode.LIGHT
    assert calls == [("accent", QColor("#778899"))]


def test_semantic_color_save_does_not_apply_qfluent_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving warning/error colors should update semantic overrides only."""

    calls: list[tuple[str, object]] = []
    semantic_calls: list[
        tuple[
            AppearanceWarningColorMode,
            AppearanceErrorColorMode,
            str | None,
            str | None,
        ]
    ] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda value: calls.append(("theme", value)))
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    monkeypatch.setattr(
        "substitute.presentation.semantic_colors.configure_semantic_color_overrides",
        lambda **kwargs: semantic_calls.append(
            (
                kwargs["warning_color_mode"],
                kwargs["error_color_mode"],
                kwargs["custom_warning_color"],
                kwargs["custom_error_color"],
            )
        ),
    )
    repository = _MemoryAppearancePreferenceRepository(
        AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color="#112233",
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )
    )
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(repository),
        resolver=_windows_resolver(),
        system_appearance_provider=_FixedSystemAppearanceProvider(),
    )

    controller.set_custom_warning_color("#ffaa00")
    resolved = controller.set_custom_error_color("#cc1122")

    assert resolved.requested.custom_warning_color == "#FFAA00"
    assert resolved.requested.custom_error_color == "#CC1122"
    assert calls == []
    assert semantic_calls == [
        (
            AppearanceWarningColorMode.CUSTOM,
            AppearanceErrorColorMode.DEFAULT,
            "#FFAA00",
            None,
        ),
        (
            AppearanceWarningColorMode.CUSTOM,
            AppearanceErrorColorMode.CUSTOM,
            "#FFAA00",
            "#CC1122",
        ),
    ]


def test_named_semantic_color_mode_save_does_not_apply_qfluent_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving Yellow/Red modes should update semantic mode state only."""

    calls: list[tuple[str, object]] = []
    semantic_calls: list[
        tuple[AppearanceWarningColorMode, AppearanceErrorColorMode]
    ] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda value: calls.append(("theme", value)))
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    monkeypatch.setattr(
        "substitute.presentation.semantic_colors.configure_semantic_color_overrides",
        lambda **kwargs: semantic_calls.append(
            (kwargs["warning_color_mode"], kwargs["error_color_mode"])
        ),
    )
    repository = _MemoryAppearancePreferenceRepository(
        AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color="#112233",
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )
    )
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(repository),
        resolver=_windows_resolver(),
        system_appearance_provider=_FixedSystemAppearanceProvider(),
    )

    controller.set_warning_color_mode(AppearanceWarningColorMode.YELLOW)
    resolved = controller.set_error_color_mode(AppearanceErrorColorMode.RED)

    assert resolved.requested.warning_color_mode is AppearanceWarningColorMode.YELLOW
    assert resolved.requested.error_color_mode is AppearanceErrorColorMode.RED
    assert calls == []
    assert semantic_calls == [
        (AppearanceWarningColorMode.YELLOW, AppearanceErrorColorMode.DEFAULT),
        (AppearanceWarningColorMode.YELLOW, AppearanceErrorColorMode.RED),
    ]


def test_each_gui_application_reprobes_system_appearance_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh Auto resolution on reload while reusing one snapshot per shell."""

    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda _value: None)
    setattr(qfluentwidgets, "setThemeColor", lambda _value: None)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)
    provider = _FixedSystemAppearanceProvider(
        SystemAppearanceSnapshot(color_scheme=SystemColorScheme.DARK)
    )
    controller = AppearanceRuntimeController(
        preference_service=AppearancePreferenceService(
            _MemoryAppearancePreferenceRepository(
                AppearancePreferences(
                    schema_version="1",
                    theme_mode=AppearanceThemeMode.AUTO,
                    accent_source=AppearanceAccentSource.SYSTEM,
                    custom_accent_color="#112233",
                    backdrop_mode=AppearanceBackdropMode.MICA_ALT,
                )
            )
        ),
        resolver=_windows_resolver(),
        system_appearance_provider=provider,
    )

    first = controller.apply_persisted_preferences()
    controller.resolve_preferences()
    provider.snapshot = SystemAppearanceSnapshot(
        color_scheme=SystemColorScheme.LIGHT,
        accent_color=RgbColor(1, 2, 3),
    )
    second = controller.apply_persisted_preferences()

    assert first.effective_theme_mode is AppearanceThemeMode.DARK
    assert second.effective_theme_mode is AppearanceThemeMode.LIGHT
    assert second.effective_accent_color == "#010203"
    assert provider.probe_count == 2
    assert controller.active_system_probe() is not None


def _windows_resolver() -> AppearanceResolver:
    """Return a resolver with current Windows material capabilities."""

    return AppearanceResolver(
        WindowMaterialCapabilities(acrylic_available=True, mica_alt_available=True)
    )


class _FixedSystemAppearanceProvider:
    """Provide mutable deterministic appearance snapshots for runtime tests."""

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
