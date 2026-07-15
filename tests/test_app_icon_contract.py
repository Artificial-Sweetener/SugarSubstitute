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

"""Contract tests for SugarSubstitute-owned Fluent-style icons."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme  # type: ignore[import-untyped]
import pytest

from substitute.presentation.resources.app_icon import (
    APP_ICON_RESOURCE_SIZES,
    AppIcon,
    app_icon_resource_path,
    application_icon,
    application_icon_ico_path,
)
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder


@pytest.mark.parametrize(
    ("icon", "base_name"),
    [
        (AppIcon.STOP_SOLID, "StopSolid"),
        (AppIcon.WINDOW_CONSOLE_20_FILLED, "WindowConsole20Filled"),
        (AppIcon.CUBE_20_FILLED, "Cube20Filled"),
        (AppIcon.PANEL_LEFT_20_FILLED, "PanelLeft20Filled"),
        (AppIcon.PANEL_LEFT_20_REGULAR, "PanelLeft20Regular"),
        (AppIcon.PANEL_RIGHT_20_FILLED, "PanelRight20Filled"),
        (AppIcon.PANEL_RIGHT_20_REGULAR, "PanelRight20Regular"),
        (AppIcon.BRAIN_CIRCUIT_20_REGULAR, "BrainCircuit20Regular"),
        (AppIcon.ERASER_20_REGULAR, "Eraser20Regular"),
        (AppIcon.ARROW_DOWNLOAD_20_REGULAR, "ArrowDownload20Regular"),
        (AppIcon.BOOK_ARROW_CLOCKWISE_20_REGULAR, "BookArrowClockwise20Regular"),
        (AppIcon.BOOK_SEARCH_20_REGULAR, "BookSearch20Regular"),
        (AppIcon.BOX_SEARCH_20_REGULAR, "BoxSearch20Regular"),
        (AppIcon.BRACES_VARIABLE_20_REGULAR, "BracesVariable20Regular"),
        (AppIcon.BROOM_20_REGULAR, "Broom20Regular"),
        (AppIcon.CERTIFICATE_20_REGULAR, "Certificate20Regular"),
        (AppIcon.CUBE_MULTIPLE_20_REGULAR, "CubeMultiple20Regular"),
        (AppIcon.CURSOR_HOVER_20_REGULAR, "CursorHover20Regular"),
        (AppIcon.DATABASE_SEARCH_20_REGULAR, "DatabaseSearch20Regular"),
        (AppIcon.DOCUMENT_TEXT_20_REGULAR, "DocumentText20Regular"),
        (AppIcon.FOLDER_OPEN_20_REGULAR, "FolderOpen20Regular"),
        (AppIcon.GLOBE_DESKTOP_20_REGULAR, "GlobeDesktop20Regular"),
        (AppIcon.HEART_20_REGULAR, "Heart20Regular"),
        (AppIcon.IMAGE_MULTIPLE_20_REGULAR, "ImageMultiple20Regular"),
        (AppIcon.IMAGE_SPARKLE_20_REGULAR, "ImageSparkle20Regular"),
        (AppIcon.KEY_20_REGULAR, "Key20Regular"),
        (AppIcon.LIBRARY_20_REGULAR, "Library20Regular"),
        (AppIcon.LINK_ADD_20_REGULAR, "LinkAdd20Regular"),
        (AppIcon.LINK_EDIT_20_REGULAR, "LinkEdit20Regular"),
        (AppIcon.PANEL_RIGHT_CURSOR_20_REGULAR, "PanelRightCursor20Regular"),
        (
            AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR,
            "PlugConnectedCheckmark20Regular",
        ),
        (
            AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
            "PlugConnectedSettings20Regular",
        ),
        (AppIcon.RATING_MATURE_20_REGULAR, "RatingMature20Regular"),
        (AppIcon.REORDER_20_REGULAR, "Reorder20Regular"),
        (AppIcon.SAVE_IMAGE_20_REGULAR, "SaveImage20Regular"),
        (AppIcon.SERVER_20_REGULAR, "Server20Regular"),
        (AppIcon.SHIELD_CHECKMARK_20_REGULAR, "ShieldCheckmark20Regular"),
        (AppIcon.STAR_20_REGULAR, "Star20Regular"),
        (AppIcon.TAG_MULTIPLE_20_REGULAR, "TagMultiple20Regular"),
        (AppIcon.TAG_SEARCH_20_REGULAR, "TagSearch20Regular"),
        (AppIcon.TEXT_ASTERISK_20_REGULAR, "TextAsterisk20Regular"),
        (
            AppIcon.TEXT_BULLET_LIST_SQUARE_SPARKLE_20_REGULAR,
            "TextBulletListSquareSparkle20Regular",
        ),
        (
            AppIcon.TEXT_BULLET_LIST_SQUARE_WARNING_20_REGULAR,
            "TextBulletListSquareWarning20Regular",
        ),
        (AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR, "TextEffectsSparkle20Regular"),
        (AppIcon.TEXT_FIELD_20_REGULAR, "TextField20Regular"),
        (
            AppIcon.TEXT_GRAMMAR_CHECKMARK_20_REGULAR,
            "TextGrammarCheckmark20Regular",
        ),
        (AppIcon.TOOLBOX_20_REGULAR, "Toolbox20Regular"),
        (AppIcon.WAND_20_REGULAR, "Wand20Regular"),
        (AppIcon.GAME_DIE_HIGH_CONTRAST, "GameDieHighContrast"),
        (AppIcon.INFINITY_HIGH_CONTRAST, "InfinityHighContrast"),
        (AppIcon.LOCKED_HIGH_CONTRAST, "LockedHighContrast"),
    ],
)
def test_app_icons_resolve_themed_svg_assets(
    icon: AppIcon,
    base_name: str,
) -> None:
    """Application icons should resolve qfluent-style SVG variants."""

    light_path = Path(icon.path(Theme.LIGHT))
    dark_path = Path(icon.path(Theme.DARK))

    assert light_path.name == f"{base_name}_black.svg"
    assert dark_path.name == f"{base_name}_white.svg"
    assert light_path.is_file()
    assert dark_path.is_file()


@pytest.mark.parametrize(
    "icon",
    [
        AppIcon.STOP_SOLID,
        AppIcon.WINDOW_CONSOLE_20_FILLED,
        AppIcon.CUBE_20_FILLED,
        AppIcon.PANEL_LEFT_20_FILLED,
        AppIcon.PANEL_LEFT_20_REGULAR,
        AppIcon.PANEL_RIGHT_20_FILLED,
        AppIcon.PANEL_RIGHT_20_REGULAR,
        AppIcon.BRAIN_CIRCUIT_20_REGULAR,
        AppIcon.ERASER_20_REGULAR,
        AppIcon.ARROW_DOWNLOAD_20_REGULAR,
        AppIcon.BOOK_ARROW_CLOCKWISE_20_REGULAR,
        AppIcon.BOOK_SEARCH_20_REGULAR,
        AppIcon.BOX_SEARCH_20_REGULAR,
        AppIcon.BRACES_VARIABLE_20_REGULAR,
        AppIcon.BROOM_20_REGULAR,
        AppIcon.CERTIFICATE_20_REGULAR,
        AppIcon.CUBE_MULTIPLE_20_REGULAR,
        AppIcon.CURSOR_HOVER_20_REGULAR,
        AppIcon.DATABASE_SEARCH_20_REGULAR,
        AppIcon.DOCUMENT_TEXT_20_REGULAR,
        AppIcon.FOLDER_OPEN_20_REGULAR,
        AppIcon.GLOBE_DESKTOP_20_REGULAR,
        AppIcon.HEART_20_REGULAR,
        AppIcon.IMAGE_MULTIPLE_20_REGULAR,
        AppIcon.IMAGE_SPARKLE_20_REGULAR,
        AppIcon.KEY_20_REGULAR,
        AppIcon.LIBRARY_20_REGULAR,
        AppIcon.LINK_ADD_20_REGULAR,
        AppIcon.LINK_EDIT_20_REGULAR,
        AppIcon.PANEL_RIGHT_CURSOR_20_REGULAR,
        AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR,
        AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
        AppIcon.RATING_MATURE_20_REGULAR,
        AppIcon.REORDER_20_REGULAR,
        AppIcon.SAVE_IMAGE_20_REGULAR,
        AppIcon.SERVER_20_REGULAR,
        AppIcon.SHIELD_CHECKMARK_20_REGULAR,
        AppIcon.STAR_20_REGULAR,
        AppIcon.TAG_MULTIPLE_20_REGULAR,
        AppIcon.TAG_SEARCH_20_REGULAR,
        AppIcon.TEXT_ASTERISK_20_REGULAR,
        AppIcon.TEXT_BULLET_LIST_SQUARE_SPARKLE_20_REGULAR,
        AppIcon.TEXT_BULLET_LIST_SQUARE_WARNING_20_REGULAR,
        AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR,
        AppIcon.TEXT_FIELD_20_REGULAR,
        AppIcon.TEXT_GRAMMAR_CHECKMARK_20_REGULAR,
        AppIcon.TOOLBOX_20_REGULAR,
        AppIcon.WAND_20_REGULAR,
        AppIcon.GAME_DIE_HIGH_CONTRAST,
        AppIcon.INFINITY_HIGH_CONTRAST,
        AppIcon.LOCKED_HIGH_CONTRAST,
    ],
)
def test_app_icon_assets_are_qfluent_recolorable(icon: AppIcon) -> None:
    """Application SVGs should use path fills so qfluent can recolor them."""

    for theme in (Theme.LIGHT, Theme.DARK):
        icon_text = Path(icon.path(theme)).read_text(encoding="utf-8")
        assert "<path " in icon_text
        assert "<rect " not in icon_text


@pytest.mark.parametrize(
    "icon",
    [
        AppIcon.STOP_SOLID,
        AppIcon.WINDOW_CONSOLE_20_FILLED,
        AppIcon.CUBE_20_FILLED,
        AppIcon.PANEL_LEFT_20_FILLED,
        AppIcon.PANEL_LEFT_20_REGULAR,
        AppIcon.PANEL_RIGHT_20_FILLED,
        AppIcon.PANEL_RIGHT_20_REGULAR,
        AppIcon.BRAIN_CIRCUIT_20_REGULAR,
        AppIcon.ERASER_20_REGULAR,
        AppIcon.ARROW_DOWNLOAD_20_REGULAR,
        AppIcon.BOOK_ARROW_CLOCKWISE_20_REGULAR,
        AppIcon.BOOK_SEARCH_20_REGULAR,
        AppIcon.BOX_SEARCH_20_REGULAR,
        AppIcon.BRACES_VARIABLE_20_REGULAR,
        AppIcon.BROOM_20_REGULAR,
        AppIcon.CERTIFICATE_20_REGULAR,
        AppIcon.CUBE_MULTIPLE_20_REGULAR,
        AppIcon.CURSOR_HOVER_20_REGULAR,
        AppIcon.DATABASE_SEARCH_20_REGULAR,
        AppIcon.DOCUMENT_TEXT_20_REGULAR,
        AppIcon.FOLDER_OPEN_20_REGULAR,
        AppIcon.GLOBE_DESKTOP_20_REGULAR,
        AppIcon.HEART_20_REGULAR,
        AppIcon.IMAGE_MULTIPLE_20_REGULAR,
        AppIcon.IMAGE_SPARKLE_20_REGULAR,
        AppIcon.KEY_20_REGULAR,
        AppIcon.LIBRARY_20_REGULAR,
        AppIcon.LINK_ADD_20_REGULAR,
        AppIcon.LINK_EDIT_20_REGULAR,
        AppIcon.PANEL_RIGHT_CURSOR_20_REGULAR,
        AppIcon.PLUG_CONNECTED_CHECKMARK_20_REGULAR,
        AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
        AppIcon.RATING_MATURE_20_REGULAR,
        AppIcon.REORDER_20_REGULAR,
        AppIcon.SAVE_IMAGE_20_REGULAR,
        AppIcon.SERVER_20_REGULAR,
        AppIcon.SHIELD_CHECKMARK_20_REGULAR,
        AppIcon.STAR_20_REGULAR,
        AppIcon.TAG_MULTIPLE_20_REGULAR,
        AppIcon.TAG_SEARCH_20_REGULAR,
        AppIcon.TEXT_ASTERISK_20_REGULAR,
        AppIcon.TEXT_BULLET_LIST_SQUARE_SPARKLE_20_REGULAR,
        AppIcon.TEXT_BULLET_LIST_SQUARE_WARNING_20_REGULAR,
        AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR,
        AppIcon.TEXT_FIELD_20_REGULAR,
        AppIcon.TEXT_GRAMMAR_CHECKMARK_20_REGULAR,
        AppIcon.TOOLBOX_20_REGULAR,
        AppIcon.WAND_20_REGULAR,
        AppIcon.GAME_DIE_HIGH_CONTRAST,
        AppIcon.INFINITY_HIGH_CONTRAST,
        AppIcon.LOCKED_HIGH_CONTRAST,
    ],
)
def test_app_icon_qicon_is_loadable(icon: AppIcon) -> None:
    """Application icons should create non-null QIcons through qfluent."""

    qicon = icon.icon(Theme.LIGHT)

    assert not qicon.isNull()


def test_panel_right_icons_use_explicit_evenodd_fill_rule() -> None:
    """Mirrored panel icons should preserve interior cutouts when Qt renders them."""

    for icon in (
        AppIcon.PANEL_RIGHT_20_FILLED,
        AppIcon.PANEL_RIGHT_20_REGULAR,
    ):
        for theme in (Theme.LIGHT, Theme.DARK):
            icon_text = Path(icon.path(theme)).read_text(encoding="utf-8")
            assert 'fill-rule="evenodd"' in icon_text
            assert 'clip-rule="evenodd"' in icon_text


def test_infinity_icon_preserves_source_viewbox_aspect() -> None:
    """The wide Fluent Emoji infinity glyph should keep its source aspect ratio."""

    icon_text = Path(AppIcon.INFINITY_HIGH_CONTRAST.path(Theme.LIGHT)).read_text(
        encoding="utf-8"
    )

    assert 'viewBox="0 0 32 32"' in icon_text


def test_app_icon_resource_paths_resolve_expected_qt_aliases() -> None:
    """Full-color app icon sizes should resolve to stable Qt resource aliases."""

    assert app_icon_resource_path(16) == ":/substitute/app/icon/16.png"
    assert app_icon_resource_path(256) == ":/substitute/app/icon/256.png"

    with pytest.raises(ValueError, match="Unsupported app icon resource size"):
        app_icon_resource_path(17)


def test_application_icon_uses_loadable_qt_resource_pixmaps() -> None:
    """The app identity icon should expose every generated Qt resource size."""

    _app()
    icon = application_icon()

    assert not icon.isNull()
    for size in APP_ICON_RESOURCE_SIZES:
        assert not icon.pixmap(size, size).isNull()


def test_application_icon_ico_path_points_to_generated_asset() -> None:
    """Future Windows packaging should have a generated executable icon file."""

    icon_path = application_icon_ico_path()

    assert icon_path.name == "app_icon.ico"
    assert icon_path.is_file()


def test_node_card_model_icon_uses_brain_circuit_app_icon() -> None:
    """Model-backed node cards should resolve to the held Brain Circuit icon."""

    icon_map = getattr(NodeCardBuilder, "_ICON_MAP")

    assert icon_map["model"] is AppIcon.BRAIN_CIRCUIT_20_REGULAR


def test_node_card_eraser_icon_uses_regular_eraser_app_icon() -> None:
    """Negative prompt cards should resolve to the held Fluent regular eraser icon."""

    icon_map = getattr(NodeCardBuilder, "_ICON_MAP")

    assert icon_map["eraser"] is AppIcon.ERASER_20_REGULAR


def test_seed_box_random_mode_uses_game_die_app_icon() -> None:
    """Random seed mode should resolve to the app-managed game die icon."""

    from substitute.presentation.widgets.seed_box import _RANDOM_SEED_ICON

    assert _RANDOM_SEED_ICON is AppIcon.GAME_DIE_HIGH_CONTRAST


def test_seed_box_fixed_mode_uses_locked_app_icon() -> None:
    """Fixed seed mode should resolve to the app-managed locked icon."""

    from substitute.presentation.widgets.seed_box import _FIXED_SEED_ICON

    assert _FIXED_SEED_ICON is AppIcon.LOCKED_HIGH_CONTRAST


def _app() -> QApplication:
    """Return the active QApplication or create one for pixmap checks."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
