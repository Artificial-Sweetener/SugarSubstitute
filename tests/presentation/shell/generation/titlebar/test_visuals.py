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

"""Test generation titlebar visual, queue, and palette contracts."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QColor, QImage, QPainter
from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButtonState,
)
import pytest

from substitute.presentation.shell.titlebar_buttons import (
    GenerationTitleBarActionCluster,
)
import substitute.presentation.shell.chrome_style as chrome_style
import substitute.presentation.shell.titlebar_buttons as titlebar_buttons
from substitute.presentation.shell.chrome_style import (
    winui_accent_button_disabled_fill_color,
    winui_accent_button_disabled_foreground_color,
    workflow_chrome_wash_color,
)

from tests.presentation.shell.generation.titlebar.support import app, presentation


def test_generation_titlebar_queue_segment_can_hide_and_restore() -> None:
    """Queue segment visibility should update cluster geometry and edge ownership."""

    app()
    cluster = GenerationTitleBarActionCluster()

    assert tuple(segment.role for segment in cluster._visible_segments()) == (
        "stop",
        "play",
        "skip",
        "queue",
    )
    assert cluster.width() == titlebar_buttons._SEGMENT_WIDTH * 4

    cluster.apply_generation_presentation(
        presentation(queue_segment_visible=False, queue_primary_enabled=True)
    )

    assert cluster.queueButton.isHidden() is True
    assert tuple(segment.role for segment in cluster._visible_segments()) == (
        "stop",
        "play",
        "skip",
    )
    assert cast(str, cluster.skipButton._edge) == "last"
    assert cluster.width() == titlebar_buttons._SEGMENT_WIDTH * 3

    cluster.apply_generation_presentation(
        presentation(queue_segment_visible=True, queue_primary_enabled=True)
    )

    assert cluster.queueButton.isHidden() is False
    assert tuple(segment.role for segment in cluster._visible_segments()) == (
        "stop",
        "play",
        "skip",
        "queue",
    )
    assert cast(str, cluster.skipButton._edge) == "middle"
    assert cluster.queueButton._edge == "last"
    assert cluster.width() == titlebar_buttons._SEGMENT_WIDTH * 4


def test_generation_titlebar_queue_visibility_preserves_availability_state() -> None:
    """Hidden queue segments should keep their enabled state when restored."""

    app()
    cluster = GenerationTitleBarActionCluster()

    cluster.apply_generation_presentation(
        presentation(
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=False,
            queue_segment_visible=False,
        )
    )

    assert cluster.queueButton.isHidden() is True
    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is False

    cluster.apply_generation_presentation(
        presentation(
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=False,
            queue_segment_visible=True,
        )
    )

    assert cluster.queueButton.isHidden() is False
    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is False

    cluster.apply_generation_presentation(
        presentation(
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=True,
            queue_segment_visible=True,
        )
    )

    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is True


def test_generation_titlebar_queue_badge_uses_theme_fill_and_accent_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue count badge should use neutral fill and accent count text."""

    app()
    cluster = GenerationTitleBarActionCluster()
    monkeypatch.setattr(titlebar_buttons, "themeColor", lambda: QColor("#0078d4"))

    cluster.apply_generation_presentation(
        presentation(queue_primary_enabled=True, queue_badge_count=12)
    )

    assert cluster.queueButton.badge_count() == 12
    assert cluster.queueButton.badge_text_color() == QColor("#0078d4")

    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: False)
    assert cluster.queueButton.badge_fill_color() == QColor("#ffffff")

    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)
    assert cluster.queueButton.badge_fill_color() == QColor("#000000")


def test_generation_titlebar_compensates_padded_icon_visual_rects() -> None:
    """Padded glyphs should use larger rects while standard FIF icons stay compact."""

    app()
    cluster = GenerationTitleBarActionCluster()

    assert cluster.playButton._icon_rect().width() == 16.0
    cluster.apply_generation_presentation(
        presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )
    assert cluster.playButton._icon_rect().width() == 24.0
    cluster.apply_generation_presentation(
        presentation(
            play_mode="end_continuous",
            play_tooltip="Stop continuous after current job",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )
    assert cluster.playButton._icon_rect().width() == 16.0
    assert cluster.skipButton._icon_rect().width() == 20.0
    assert cluster.queueButton._icon_rect().width() == 16.0
    assert cluster.stopButton._icon_rect().width() == 16.0


def test_generation_titlebar_cluster_uses_theme_aware_segment_icon_contrast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segment icons should share the same theme-contrast policy across roles."""

    app()
    cluster = GenerationTitleBarActionCluster()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: False)

    assert cluster.playButton._icon_color() == QColor("#ffffff")
    assert cluster.skipButton._icon_color() == QColor("#ffffff")
    assert cluster.queueButton._icon_color() == QColor("#ffffff")
    assert cluster.stopButton._icon_color() == QColor("#ffffff")

    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)

    assert cluster.playButton._icon_color() == QColor("#000000")
    assert cluster.skipButton._icon_color() == QColor("#000000")
    assert cluster.queueButton._icon_color() == QColor("#000000")
    assert cluster.stopButton._icon_color() == QColor("#000000")
    assert cluster.divider_color == QColor(0, 0, 0, 82)
    assert cluster.bottom_inset == 2.0


def test_generation_titlebar_cluster_uses_winui_disabled_accent_palette_without_hover_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled actions should use disabled accent colors without hover response."""

    app()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: False)
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    cluster = GenerationTitleBarActionCluster()
    cluster.apply_generation_presentation(
        presentation(
            play_enabled=False,
            stop_enabled=False,
            skip_enabled=False,
            queue_primary_enabled=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )

    disabled_fill = winui_accent_button_disabled_fill_color()
    disabled_foreground = winui_accent_button_disabled_foreground_color()
    assert cluster.stopButton._icon_color() == disabled_foreground
    assert cluster.playButton._icon_color() == disabled_foreground
    assert cluster.skipButton._icon_color() == disabled_foreground
    assert cluster.queueButton._icon_color() == disabled_foreground
    assert cluster.stopButton._segment_fill_color() == disabled_fill
    assert cluster.playButton._segment_fill_color() == disabled_fill
    assert cluster.skipButton._segment_fill_color() == disabled_fill
    assert cluster.queueButton._segment_fill_color() == disabled_fill
    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is False

    cluster.skipButton.setState(TitleBarButtonState.HOVER)
    assert cluster.skipButton._segment_fill_color() == disabled_fill

    cluster.skipButton.setState(TitleBarButtonState.PRESSED)
    assert cluster.skipButton._segment_fill_color() == disabled_fill


def test_generation_titlebar_disabled_skip_icon_still_renders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabled custom SVG icons should keep visible pixels while using alpha."""

    app()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    cluster = GenerationTitleBarActionCluster()
    cluster.apply_generation_presentation(
        presentation(
            play_enabled=False,
            stop_enabled=False,
            skip_enabled=False,
            queue_primary_enabled=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )

    image = QImage(
        cluster.skipButton.size(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    cluster.skipButton._render_icon(
        painter,
        cluster.skipButton._icon_rect(),
        cluster.skipButton._icon_color(),
    )
    painter.end()

    painted_pixels = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() > 0:
                painted_pixels += 1

    assert painted_pixels > 0


def test_generation_titlebar_cluster_uses_acrylic_specific_surface_and_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic clusters should keep the wash surface and accent-colored icons."""

    app()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)
    monkeypatch.setattr(titlebar_buttons, "themeColor", lambda: QColor("#E91E63"))
    cluster = GenerationTitleBarActionCluster(acrylic_style_enabled=True)

    assert cluster.uses_acrylic_style() is True
    assert cluster._cluster_surface_color() == QColor(
        *workflow_chrome_wash_color("acrylic")
    )
    assert cluster.accent_color() == QColor("#E91E63")
    assert cluster.playButton._icon_color() == QColor("#E91E63")
    assert cluster.playButton.getNormalBackgroundColor() == QColor(0, 0, 0, 0)
