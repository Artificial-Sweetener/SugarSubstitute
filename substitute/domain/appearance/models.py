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

"""Define persisted appearance preferences and stable default values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

APPEARANCE_PREFERENCES_SCHEMA_VERSION = "3"
DEFAULT_CUSTOM_ACCENT_COLOR = "#E91E63"
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class AppearanceThemeMode(Enum):
    """Identify the user-selected application theme behavior."""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class AppearanceAccentSource(Enum):
    """Identify how the runtime accent color is chosen."""

    CUSTOM = "custom"
    SYSTEM = "system"


class AppearanceBackdropMode(Enum):
    """Identify the preferred native window material for supported shells."""

    MICA_ALT = "mica_alt"
    ACRYLIC = "acrylic"


class AppearanceWarningColorMode(Enum):
    """Identify how the warning semantic color is chosen."""

    DEFAULT = "default"
    YELLOW = "yellow"
    CUSTOM = "custom"


class AppearanceErrorColorMode(Enum):
    """Identify how the error semantic color is chosen."""

    DEFAULT = "default"
    RED = "red"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class RgbColor:
    """Represent an sRGB color without presentation toolkit dependencies."""

    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        """Reject channel values outside the sRGB byte range."""

        for channel_name, channel_value in (
            ("red", self.red),
            ("green", self.green),
            ("blue", self.blue),
        ):
            if channel_value < 0 or channel_value > 255:
                raise ValueError(f"{channel_name} must be between 0 and 255.")

    @classmethod
    def from_hex(cls, color: str) -> RgbColor:
        """Return an RGB color parsed from a `#RRGGBB` string."""

        normalized = color.strip()
        if _HEX_COLOR_PATTERN.fullmatch(normalized) is None:
            raise ValueError("color must use #RRGGBB hex syntax.")
        return cls(
            red=int(normalized[1:3], 16),
            green=int(normalized[3:5], 16),
            blue=int(normalized[5:7], 16),
        )

    def to_hex(self) -> str:
        """Return the color formatted as uppercase `#RRGGBB` text."""

        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"


@dataclass(frozen=True, slots=True)
class SemanticPalette:
    """Expose derived semantic colors for presentation diagnostics."""

    accent: RgbColor
    error_foreground: RgbColor
    warning_foreground: RgbColor


@dataclass(frozen=True, slots=True)
class AppearancePreferences:
    """Capture the persisted user appearance preferences."""

    schema_version: str
    theme_mode: AppearanceThemeMode
    accent_source: AppearanceAccentSource
    custom_accent_color: str
    backdrop_mode: AppearanceBackdropMode
    warning_color_mode: AppearanceWarningColorMode = AppearanceWarningColorMode.DEFAULT
    error_color_mode: AppearanceErrorColorMode = AppearanceErrorColorMode.DEFAULT
    custom_warning_color: str | None = None
    custom_error_color: str | None = None

    def with_theme_mode(
        self,
        theme_mode: AppearanceThemeMode,
    ) -> AppearancePreferences:
        """Return a copy with one requested theme mode updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=self.error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> AppearancePreferences:
        """Return a copy with one requested accent source updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=self.error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_custom_accent_color(
        self,
        custom_accent_color: str,
    ) -> AppearancePreferences:
        """Return a copy with one requested custom accent color updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=self.error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_warning_color_mode(
        self,
        warning_color_mode: AppearanceWarningColorMode,
    ) -> AppearancePreferences:
        """Return a copy with one warning color mode updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=warning_color_mode,
            error_color_mode=self.error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_error_color_mode(
        self,
        error_color_mode: AppearanceErrorColorMode,
    ) -> AppearancePreferences:
        """Return a copy with one error color mode updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_custom_warning_color(
        self,
        custom_warning_color: str | None,
    ) -> AppearancePreferences:
        """Return a copy with one requested warning color override updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=(
                AppearanceWarningColorMode.CUSTOM
                if custom_warning_color is not None
                else AppearanceWarningColorMode.DEFAULT
            ),
            error_color_mode=self.error_color_mode,
            custom_warning_color=custom_warning_color,
            custom_error_color=self.custom_error_color,
        )

    def with_custom_error_color(
        self,
        custom_error_color: str | None,
    ) -> AppearancePreferences:
        """Return a copy with one requested error color override updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=self.backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=(
                AppearanceErrorColorMode.CUSTOM
                if custom_error_color is not None
                else AppearanceErrorColorMode.DEFAULT
            ),
            custom_warning_color=self.custom_warning_color,
            custom_error_color=custom_error_color,
        )

    def with_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> AppearancePreferences:
        """Return a copy with one requested backdrop mode updated."""

        return AppearancePreferences(
            schema_version=self.schema_version,
            theme_mode=self.theme_mode,
            accent_source=self.accent_source,
            custom_accent_color=self.custom_accent_color,
            backdrop_mode=backdrop_mode,
            warning_color_mode=self.warning_color_mode,
            error_color_mode=self.error_color_mode,
            custom_warning_color=self.custom_warning_color,
            custom_error_color=self.custom_error_color,
        )


def default_appearance_preferences() -> AppearancePreferences:
    """Return the stable default appearance preferences for a fresh install."""

    return AppearancePreferences(
        schema_version=APPEARANCE_PREFERENCES_SCHEMA_VERSION,
        theme_mode=AppearanceThemeMode.AUTO,
        accent_source=AppearanceAccentSource.SYSTEM,
        custom_accent_color=DEFAULT_CUSTOM_ACCENT_COLOR,
        backdrop_mode=AppearanceBackdropMode.MICA_ALT,
    )


__all__ = [
    "APPEARANCE_PREFERENCES_SCHEMA_VERSION",
    "DEFAULT_CUSTOM_ACCENT_COLOR",
    "AppearanceAccentSource",
    "AppearanceBackdropMode",
    "AppearanceErrorColorMode",
    "AppearancePreferences",
    "AppearanceThemeMode",
    "AppearanceWarningColorMode",
    "RgbColor",
    "SemanticPalette",
    "default_appearance_preferences",
]
