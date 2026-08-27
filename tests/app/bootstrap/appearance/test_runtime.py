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

"""Test runtime appearance orchestration at GUI lifecycle boundaries."""

from __future__ import annotations

import pytest

import substitute.app.bootstrap.appearance_runtime as appearance_runtime_module
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceErrorColorMode,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    RgbColor,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)
from tests.application.appearance.support import (
    FixedSystemAppearanceProvider,
    appearance_preferences,
    appearance_runtime,
)

SemanticPublication = tuple[
    AppearanceWarningColorMode,
    AppearanceErrorColorMode,
    str | None,
    str | None,
]


class AppearancePublicationRecorder:
    """Record appearance values published through bootstrap output boundaries."""

    def __init__(self) -> None:
        """Initialize empty theme, accent, and semantic publications."""

        self.themes: list[tuple[AppearanceThemeMode, str]] = []
        self.accents: list[str] = []
        self.semantic_colors: list[SemanticPublication] = []

    def configure_theme(
        self,
        *,
        theme_mode: AppearanceThemeMode,
        accent_color: str,
    ) -> None:
        """Record one complete shell theme publication."""

        self.themes.append((theme_mode, accent_color))

    def configure_accent_color(self, *, accent_color: str) -> None:
        """Record one live accent publication."""

        self.accents.append(accent_color)

    def configure_semantic_colors(
        self,
        *,
        warning_color_mode: AppearanceWarningColorMode,
        error_color_mode: AppearanceErrorColorMode,
        custom_warning_color: str | None,
        custom_error_color: str | None,
    ) -> None:
        """Record one live semantic-color publication."""

        self.semantic_colors.append(
            (
                warning_color_mode,
                error_color_mode,
                custom_warning_color,
                custom_error_color,
            )
        )


@pytest.fixture
def appearance_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> AppearancePublicationRecorder:
    """Record bootstrap output without replacing installed module identities."""

    recorder = AppearancePublicationRecorder()
    monkeypatch.setattr(
        appearance_runtime_module,
        "configure_theme",
        recorder.configure_theme,
    )
    monkeypatch.setattr(
        appearance_runtime_module,
        "configure_accent_color",
        recorder.configure_accent_color,
    )
    monkeypatch.setattr(
        "substitute.presentation.semantic_colors.configure_semantic_color_overrides",
        recorder.configure_semantic_colors,
    )
    return recorder


def test_runtime_controller_applies_resolved_persisted_appearance(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Publish resolved persisted appearance once during shell startup."""

    controller = appearance_runtime(
        preferences=appearance_preferences(
            theme_mode=AppearanceThemeMode.AUTO,
            accent_source=AppearanceAccentSource.SYSTEM,
        ),
        provider=FixedSystemAppearanceProvider(
            SystemAppearanceSnapshot(
                color_scheme=SystemColorScheme.LIGHT,
                accent_color=RgbColor.from_hex("#445566"),
            )
        ),
    )

    resolved = controller.apply_persisted_preferences()

    assert resolved.effective_theme_mode is AppearanceThemeMode.LIGHT
    assert resolved.effective_accent_color == "#445566"
    assert appearance_publications.themes == [(AppearanceThemeMode.LIGHT, "#445566")]
    assert appearance_publications.accents == []
    assert appearance_publications.semantic_colors == [
        (
            AppearanceWarningColorMode.DEFAULT,
            AppearanceErrorColorMode.DEFAULT,
            None,
            None,
        )
    ]


def test_theme_mode_save_does_not_publish_live_appearance(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Wait for GUI reload before publishing a saved theme mode."""

    controller = appearance_runtime()

    resolved = controller.set_theme_mode(AppearanceThemeMode.LIGHT)

    assert resolved.requested.theme_mode is AppearanceThemeMode.LIGHT
    assert appearance_publications.themes == []
    assert appearance_publications.accents == []
    assert appearance_publications.semantic_colors == []


def test_accent_save_does_not_publish_pending_theme_mode(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Publish an accent without dragging a pending theme into the live shell."""

    controller = appearance_runtime()

    controller.set_theme_mode(AppearanceThemeMode.LIGHT)
    resolved = controller.set_custom_accent_color("#778899")

    assert resolved.requested.theme_mode is AppearanceThemeMode.LIGHT
    assert appearance_publications.themes == []
    assert appearance_publications.accents == ["#778899"]
    assert len(appearance_publications.semantic_colors) == 1


def test_custom_semantic_color_saves_do_not_publish_qfluent_appearance(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Publish custom semantic colors without changing theme or accent state."""

    controller = appearance_runtime()

    controller.set_custom_warning_color("#ffaa00")
    resolved = controller.set_custom_error_color("#cc1122")

    assert resolved.requested.custom_warning_color == "#FFAA00"
    assert resolved.requested.custom_error_color == "#CC1122"
    assert appearance_publications.themes == []
    assert appearance_publications.accents == []
    assert appearance_publications.semantic_colors == [
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


def test_named_semantic_color_modes_do_not_publish_qfluent_appearance(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Publish named semantic modes without changing theme or accent state."""

    controller = appearance_runtime()

    controller.set_warning_color_mode(AppearanceWarningColorMode.YELLOW)
    resolved = controller.set_error_color_mode(AppearanceErrorColorMode.RED)

    assert resolved.requested.warning_color_mode is AppearanceWarningColorMode.YELLOW
    assert resolved.requested.error_color_mode is AppearanceErrorColorMode.RED
    assert appearance_publications.themes == []
    assert appearance_publications.accents == []
    assert appearance_publications.semantic_colors == [
        (
            AppearanceWarningColorMode.YELLOW,
            AppearanceErrorColorMode.DEFAULT,
            None,
            None,
        ),
        (
            AppearanceWarningColorMode.YELLOW,
            AppearanceErrorColorMode.RED,
            None,
            None,
        ),
    ]


def test_each_gui_application_reprobes_system_appearance_once(
    appearance_publications: AppearancePublicationRecorder,
) -> None:
    """Refresh Auto resolution on reload while reusing one probe per shell."""

    provider = FixedSystemAppearanceProvider(
        SystemAppearanceSnapshot(color_scheme=SystemColorScheme.DARK)
    )
    controller = appearance_runtime(
        preferences=appearance_preferences(
            theme_mode=AppearanceThemeMode.AUTO,
            accent_source=AppearanceAccentSource.SYSTEM,
        ),
        provider=provider,
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
    assert appearance_publications.themes == [
        (AppearanceThemeMode.DARK, "#E91E63"),
        (AppearanceThemeMode.LIGHT, "#010203"),
    ]
