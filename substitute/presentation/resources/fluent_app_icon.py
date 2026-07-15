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

"""Expose SugarSubstitute-owned Fluent-style icon resources."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

# qfluentwidgets does not ship typing metadata, but AppIcon must inherit its
# runtime base class to behave like qfluent FluentIcon entries at call sites.
from qfluentwidgets import FluentIconBase, Theme, getIconColor  # type: ignore[import-untyped]

_ICON_DIR = Path(__file__).resolve().parent / "icons"


class AppIcon(FluentIconBase, Enum):  # type: ignore[misc]
    """Application-owned Fluent-style icons."""

    STOP_SOLID = "StopSolid"
    WINDOW_CONSOLE_20_FILLED = "WindowConsole20Filled"
    CUBE_20_FILLED = "Cube20Filled"
    NEXT_24_FILLED = "Next24Filled"
    PANEL_LEFT_20_FILLED = "PanelLeft20Filled"
    PANEL_LEFT_20_REGULAR = "PanelLeft20Regular"
    PANEL_RIGHT_20_FILLED = "PanelRight20Filled"
    PANEL_RIGHT_20_REGULAR = "PanelRight20Regular"
    BRAIN_CIRCUIT_20_REGULAR = "BrainCircuit20Regular"
    ERASER_20_REGULAR = "Eraser20Regular"
    ARROW_DOWNLOAD_20_REGULAR = "ArrowDownload20Regular"
    BOOK_ARROW_CLOCKWISE_20_REGULAR = "BookArrowClockwise20Regular"
    BOOK_SEARCH_20_REGULAR = "BookSearch20Regular"
    BOX_SEARCH_20_REGULAR = "BoxSearch20Regular"
    BRACES_VARIABLE_20_REGULAR = "BracesVariable20Regular"
    BROOM_20_REGULAR = "Broom20Regular"
    CERTIFICATE_20_REGULAR = "Certificate20Regular"
    CUBE_MULTIPLE_20_REGULAR = "CubeMultiple20Regular"
    CURSOR_HOVER_20_REGULAR = "CursorHover20Regular"
    DATABASE_SEARCH_20_REGULAR = "DatabaseSearch20Regular"
    DOCUMENT_TEXT_20_REGULAR = "DocumentText20Regular"
    FOLDER_OPEN_20_REGULAR = "FolderOpen20Regular"
    GLOBE_DESKTOP_20_REGULAR = "GlobeDesktop20Regular"
    HEART_20_REGULAR = "Heart20Regular"
    IMAGE_MULTIPLE_20_REGULAR = "ImageMultiple20Regular"
    IMAGE_SPARKLE_20_REGULAR = "ImageSparkle20Regular"
    KEY_20_REGULAR = "Key20Regular"
    LIBRARY_20_REGULAR = "Library20Regular"
    LINK_ADD_20_REGULAR = "LinkAdd20Regular"
    LINK_EDIT_20_REGULAR = "LinkEdit20Regular"
    PANEL_RIGHT_CURSOR_20_REGULAR = "PanelRightCursor20Regular"
    PLUG_CONNECTED_CHECKMARK_20_REGULAR = "PlugConnectedCheckmark20Regular"
    PLUG_CONNECTED_SETTINGS_20_REGULAR = "PlugConnectedSettings20Regular"
    RATING_MATURE_20_REGULAR = "RatingMature20Regular"
    REORDER_20_REGULAR = "Reorder20Regular"
    SAVE_IMAGE_20_REGULAR = "SaveImage20Regular"
    SERVER_20_REGULAR = "Server20Regular"
    SHIELD_CHECKMARK_20_REGULAR = "ShieldCheckmark20Regular"
    STAR_20_REGULAR = "Star20Regular"
    TAG_MULTIPLE_20_REGULAR = "TagMultiple20Regular"
    TAG_SEARCH_20_REGULAR = "TagSearch20Regular"
    TEXT_ASTERISK_20_REGULAR = "TextAsterisk20Regular"
    TEXT_BULLET_LIST_SQUARE_SPARKLE_20_REGULAR = "TextBulletListSquareSparkle20Regular"
    TEXT_BULLET_LIST_SQUARE_WARNING_20_REGULAR = "TextBulletListSquareWarning20Regular"
    TEXT_EFFECTS_SPARKLE_20_REGULAR = "TextEffectsSparkle20Regular"
    TEXT_FIELD_20_REGULAR = "TextField20Regular"
    TEXT_GRAMMAR_CHECKMARK_20_REGULAR = "TextGrammarCheckmark20Regular"
    TOOLBOX_20_REGULAR = "Toolbox20Regular"
    WAND_20_REGULAR = "Wand20Regular"
    GAME_DIE_HIGH_CONTRAST = "GameDieHighContrast"
    INFINITY_HIGH_CONTRAST = "InfinityHighContrast"
    LOCKED_HIGH_CONTRAST = "LockedHighContrast"

    def path(self, theme: Theme = Theme.AUTO) -> str:
        """Return the themed SVG path for this application-owned icon."""

        icon_path = _ICON_DIR / f"{self.value}_{getIconColor(theme)}.svg"
        if not icon_path.is_file():
            raise FileNotFoundError(f"Missing application icon asset: {icon_path}")
        return str(icon_path)


__all__ = ["AppIcon"]
