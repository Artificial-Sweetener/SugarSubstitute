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

"""Expose appearance preference services and runtime normalization policies."""

from substitute.application.appearance.appearance_preference_service import (
    AppearancePreferenceService,
)
from substitute.application.appearance.active_appearance_baseline import (
    ActiveAppearanceBaseline,
    ActiveAppearanceSnapshot,
)
from substitute.application.appearance.appearance_restart_coordinator import (
    AppearanceRestartCoordinator,
)
from substitute.application.appearance.appearance_resolver import (
    AppearanceCapabilities,
    AppearanceResolver,
    ResolvedAppearance,
)
from substitute.application.appearance.window_material_capabilities import (
    WindowMaterialCapabilities,
)
from substitute.application.appearance.semantic_palette import (
    derive_semantic_palette,
    resolve_semantic_palette,
)
from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    RgbColor,
    SemanticPalette,
)

__all__ = [
    "AppearanceCapabilities",
    "AppearanceAccentSource",
    "ActiveAppearanceBaseline",
    "ActiveAppearanceSnapshot",
    "AppearanceBackdropMode",
    "AppearanceErrorColorMode",
    "AppearancePreferenceService",
    "AppearancePreferences",
    "AppearanceRestartCoordinator",
    "AppearanceResolver",
    "ResolvedAppearance",
    "AppearanceThemeMode",
    "AppearanceWarningColorMode",
    "DEFAULT_CUSTOM_ACCENT_COLOR",
    "RgbColor",
    "SemanticPalette",
    "derive_semantic_palette",
    "resolve_semantic_palette",
    "WindowMaterialCapabilities",
]
