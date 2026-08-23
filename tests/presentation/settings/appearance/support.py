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

"""Provide appearance runtime fakes and layout assertions for Settings tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import ComboBox, PushButton  # type: ignore[import-untyped]

from substitute.application.appearance import AppearanceResolver, ResolvedAppearance
from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    SystemAppearanceSnapshot,
)
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
)
from substitute.presentation.settings.settings_segmented_card import (
    SettingsSegmentedCard,
    SettingsSegmentedCardRow,
)
from tests.support.qt.lifecycle import activate_widget_layouts


class AppearanceRuntime:
    """Store appearance preferences while exposing production resolution."""

    def __init__(self) -> None:
        """Initialize dark custom-accent appearance preferences."""

        self._preferences = AppearancePreferences(
            schema_version="1",
            theme_mode=AppearanceThemeMode.DARK,
            accent_source=AppearanceAccentSource.CUSTOM,
            custom_accent_color=DEFAULT_CUSTOM_ACCENT_COLOR,
            backdrop_mode=AppearanceBackdropMode.MICA_ALT,
        )

    def load_preferences(self) -> AppearancePreferences:
        """Return current appearance preferences."""

        return self._preferences

    def resolve_preferences(self) -> ResolvedAppearance:
        """Resolve current preferences against a stable system snapshot."""

        return AppearanceResolver().resolve(
            self._preferences,
            system_appearance=SystemAppearanceSnapshot(),
        )

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> ResolvedAppearance:
        """Persist and resolve one theme mode."""

        self._preferences = self._preferences.with_theme_mode(theme_mode)
        return self.resolve_preferences()

    def set_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> ResolvedAppearance:
        """Persist and resolve one accent source."""

        self._preferences = self._preferences.with_accent_source(accent_source)
        return self.resolve_preferences()

    def set_custom_accent_color(self, color: str) -> ResolvedAppearance:
        """Persist and resolve one custom accent color."""

        self._preferences = self._preferences.with_custom_accent_color(color)
        return self.resolve_preferences()

    def set_custom_warning_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and resolve one custom warning color."""

        self._preferences = self._preferences.with_custom_warning_color(color)
        return self.resolve_preferences()

    def set_warning_color_mode(
        self,
        mode: AppearanceWarningColorMode,
    ) -> ResolvedAppearance:
        """Persist and resolve one warning color mode."""

        self._preferences = self._preferences.with_warning_color_mode(mode)
        return self.resolve_preferences()

    def set_custom_error_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and resolve one custom error color."""

        self._preferences = self._preferences.with_custom_error_color(color)
        return self.resolve_preferences()

    def set_error_color_mode(
        self,
        mode: AppearanceErrorColorMode,
    ) -> ResolvedAppearance:
        """Persist and resolve one error color mode."""

        self._preferences = self._preferences.with_error_color_mode(mode)
        return self.resolve_preferences()

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> ResolvedAppearance:
        """Persist and resolve one backdrop mode."""

        self._preferences = self._preferences.with_backdrop_mode(backdrop_mode)
        return self.resolve_preferences()


class RecordingAppearanceRestartCoordinator:
    """Record restart-required appearance saves."""

    def __init__(self) -> None:
        """Create an empty save log."""

        self.saved: list[tuple[str, object]] = []

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> PendingSnapshot:
        """Record a theme-mode save."""

        self.saved.append(("theme", theme_mode))
        return PendingSnapshot(count=0)

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> PendingSnapshot:
        """Record a backdrop-mode save."""

        self.saved.append(("backdrop", backdrop_mode))
        return PendingSnapshot(count=0)


class PendingSnapshot:
    """Expose a minimal pending restart count."""

    def __init__(self, *, count: int) -> None:
        """Store the pending item count."""

        self.count = count


class FakeColorSignal:
    """Capture and replay one color dialog callback."""

    def __init__(self) -> None:
        """Create an unconnected signal double."""

        self._callback: Callable[[QColor], None] | None = None

    def connect(self, callback: Callable[[QColor], None]) -> None:
        """Record the connected callback."""

        self._callback = callback

    def emit(self, color: QColor) -> None:
        """Publish one selected color."""

        if self._callback is not None:
            self._callback(color)


class FakeColorDialog:
    """Emit a configured color when the dialog executes."""

    def __init__(self, *, color: str, title: str, parent: object) -> None:
        """Store dialog arguments and its selected color."""

        self._color = QColor(color)
        self.title = title
        self.parent = parent
        self.colorChanged = FakeColorSignal()

    def exec(self) -> int:
        """Emit the selected color and accept the dialog."""

        self.colorChanged.emit(self._color)
        return 1


def settings_control(page: SettingsPageEntry, setting_id: str) -> SettingsControlEntry:
    """Return one catalog control by stable setting identifier."""

    for section in page.sections:
        for control in section.controls:
            if control.setting_id == setting_id:
                return control
    raise AssertionError(f"Missing Settings control: {setting_id}")


def label_texts(widget: QWidget) -> tuple[str, ...]:
    """Return all non-empty labels below one widget."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )


def segmented_row_with_title(
    card: SettingsSegmentedCard,
    title: str,
) -> SettingsSegmentedCardRow:
    """Return the segmented row containing one title."""

    for row in card.findChildren(SettingsSegmentedCardRow):
        if title in label_texts(row):
            return row
    raise AssertionError(f"Missing segmented row: {title}")


def segmented_rows(
    card: SettingsSegmentedCard,
) -> tuple[SettingsSegmentedCardRow, ...]:
    """Return typed rows owned by one segmented card."""

    rows = card.rows()
    assert all(isinstance(row, SettingsSegmentedCardRow) for row in rows)
    return tuple(cast(SettingsSegmentedCardRow, row) for row in rows)


def segmented_row_titles(card: SettingsSegmentedCard) -> tuple[str, ...]:
    """Return visible System color row titles."""

    titles = []
    expected = {"Accent color", "Warning color", "Error color"}
    for row in card.findChildren(SettingsSegmentedCardRow):
        for label in row.findChildren(QLabel):
            text = label.text().strip()
            if text in expected:
                titles.append(text)
                break
    return tuple(titles)


def assert_system_color_controls_aligned(card: SettingsSegmentedCard) -> None:
    """Assert System color trailing controls share visual columns."""

    rows = (
        segmented_row_with_title(card, "Accent color"),
        segmented_row_with_title(card, "Warning color"),
        segmented_row_with_title(card, "Error color"),
    )
    combo_names = (
        "AppearanceAccentSourceCombo",
        "AppearanceWarningModeCombo",
        "AppearanceErrorModeCombo",
    )
    button_names = (
        "AppearanceAccentChooseButton",
        "AppearanceWarningChooseButton",
        "AppearanceErrorChooseButton",
    )
    swatches = tuple(
        single_child(row, QWidget, "AppearanceColorSwatch") for row in rows
    )
    combos = tuple(
        single_child(row, ComboBox, name)
        for row, name in zip(rows, combo_names, strict=True)
    )
    buttons = tuple(
        single_child(row, PushButton, name)
        for row, name in zip(rows, button_names, strict=True)
    )

    assert (
        mapped_x_positions(card, swatches)
        == (swatches[0].mapTo(card, QPoint()).x(),) * 3
    )
    assert (
        mapped_x_positions(card, combos) == (combos[0].mapTo(card, QPoint()).x(),) * 3
    )
    assert (
        mapped_x_positions(card, buttons) == (buttons[0].mapTo(card, QPoint()).x(),) * 3
    )


def single_child[TWidget: QWidget](
    parent: QObject,
    widget_type: type[TWidget],
    name: str,
) -> TWidget:
    """Return one named child widget."""

    child = parent.findChild(widget_type, name)
    assert child is not None
    return child


def mapped_x_positions(
    ancestor: QWidget,
    widgets: tuple[QWidget, ...],
) -> tuple[int, ...]:
    """Map child x positions into a shared ancestor."""

    return tuple(widget.mapTo(ancestor, QPoint()).x() for widget in widgets)


def activate_system_color_layout(card: SettingsSegmentedCard, parent: QWidget) -> None:
    """Resolve the card's current geometry without draining unrelated Qt work."""

    activate_widget_layouts(parent, card, *segmented_rows(card))
