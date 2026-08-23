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

"""Test generation titlebar action-cluster behavior."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QTranslator, Qt
from PySide6.QtTest import QTest
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

import substitute.presentation.resources.app_icon as app_icon_module
from substitute.presentation.shell.titlebar_buttons import (
    GenerationTitleBarActionCluster,
)
from substitute.presentation.resources.app_icon import AppIcon
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter

from tests.presentation.shell.generation.titlebar.support import app, presentation


def test_generation_titlebar_cluster_emits_segment_intents() -> None:
    """Left-clicking each segment should emit its command intent."""

    app()
    cluster = GenerationTitleBarActionCluster()
    play_calls: list[bool] = []
    skip_calls: list[bool] = []
    queue_calls: list[bool] = []
    stop_calls: list[bool] = []
    cluster.playClicked.connect(lambda: play_calls.append(True))
    cluster.skipClicked.connect(lambda: skip_calls.append(True))
    cluster.queueClicked.connect(lambda: queue_calls.append(True))
    cluster.stopClicked.connect(lambda: stop_calls.append(True))

    QTest.mouseClick(cluster.playButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(cluster.skipButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(cluster.queueButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(cluster.stopButton, Qt.MouseButton.LeftButton)

    assert play_calls == [True]
    assert skip_calls == [True]
    assert queue_calls == [True]
    assert stop_calls == [True]
    assert cluster.queue_button_target() is cluster.queueButton


def test_generation_titlebar_play_right_click_requests_mode_menu_only() -> None:
    """Right-clicking play should not emit the normal play command."""

    app()
    cluster = GenerationTitleBarActionCluster()
    cluster.playButton.rightClicked.disconnect()
    play_calls: list[bool] = []
    menu_calls: list[bool] = []
    cluster.playClicked.connect(lambda: play_calls.append(True))
    cluster.playButton.rightClicked.connect(lambda: menu_calls.append(True))

    QTest.mouseClick(cluster.playButton, Qt.MouseButton.RightButton)

    assert play_calls == []
    assert menu_calls == [True]


def test_generation_titlebar_queue_right_click_requests_context_menu_only() -> None:
    """Right-clicking queue should not emit the normal queue dropdown command."""

    app()
    cluster = GenerationTitleBarActionCluster()
    queue_calls: list[bool] = []
    context_calls: list[bool] = []
    cluster.queueClicked.connect(lambda: queue_calls.append(True))
    cluster.queueContextMenuRequested.connect(lambda: context_calls.append(True))

    QTest.mouseClick(cluster.queueButton, Qt.MouseButton.RightButton)

    assert queue_calls == []
    assert context_calls == [True]


def test_generation_titlebar_disabled_queue_still_allows_context_menu() -> None:
    """Disabled queue primary action should still leave right-click controls reachable."""

    app()
    cluster = GenerationTitleBarActionCluster()
    queue_calls: list[bool] = []
    context_calls: list[bool] = []
    cluster.queueClicked.connect(lambda: queue_calls.append(True))
    cluster.queueContextMenuRequested.connect(lambda: context_calls.append(True))
    cluster.apply_generation_presentation(
        presentation(
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=False,
        )
    )

    QTest.mouseClick(cluster.queueButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(cluster.queueButton, Qt.MouseButton.RightButton)

    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is False
    assert queue_calls == []
    assert context_calls == [True]


def test_generation_titlebar_mode_actions_emit_mode_selection() -> None:
    """Mode menu actions should only select Generate or Continuous."""

    app()
    cluster = GenerationTitleBarActionCluster()
    selected_modes: list[str] = []
    cluster.generateModeSelected.connect(lambda mode: selected_modes.append(mode))

    cluster._action_generate.trigger()
    cluster._action_continuous.trigger()

    assert selected_modes == ["generate", "continuous"]
    assert not hasattr(cluster, "_action_scenes")


def test_generation_titlebar_cluster_applies_presentation_state() -> None:
    """The cluster should expose projected tooltips and action availability."""

    app()
    cluster = GenerationTitleBarActionCluster()
    play_tooltip_filter = cluster.playButton._tooltip_filter

    cluster.apply_generation_presentation(presentation(play_mode="generate"))
    assert cluster.playButton.toolTip() == "Generate"
    assert cluster.playButton._tooltip_filter is play_tooltip_filter

    cluster.apply_generation_presentation(
        presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )
    assert cluster.playButton.toolTip() == "Continuous"
    assert cluster.playButton._tooltip_filter is play_tooltip_filter
    assert cluster.playButton._icon is AppIcon.INFINITY_HIGH_CONTRAST

    cluster.apply_generation_presentation(
        presentation(
            play_mode="end_continuous",
            play_tooltip="Stop continuous after current job",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )
    assert cluster.playButton.toolTip() == "Stop continuous after current job"
    assert cluster.playButton._tooltip_filter is play_tooltip_filter
    assert cluster.playButton._icon is FIF.PAUSE_BOLD

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
    assert cluster.playButton.isEnabled() is False
    assert cluster.skipButton.isEnabled() is False
    assert cluster.queueButton.isEnabled() is True
    assert cluster.stopButton.isEnabled() is False
    assert cluster._action_generate.isEnabled() is False
    assert cluster._action_continuous.isEnabled() is False

    cluster.apply_generation_presentation(
        presentation(
            play_enabled=True,
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=False,
            mode_menu_enabled=True,
        )
    )
    assert cluster.playButton.isEnabled() is True
    assert cluster.skipButton.isEnabled() is True
    assert cluster.queueButton.isEnabled() is True
    assert cluster.queueButton.primary_action_enabled() is False
    assert cluster.stopButton.isEnabled() is True
    assert cluster._action_generate.isEnabled() is True
    assert cluster._action_continuous.isEnabled() is True

    cluster.apply_generation_presentation(
        presentation(
            play_enabled=True,
            stop_enabled=True,
            skip_enabled=True,
            queue_primary_enabled=False,
            mode_menu_enabled=False,
        )
    )
    assert cluster.playButton.isEnabled() is True
    assert cluster._action_generate.isEnabled() is False
    assert cluster._action_continuous.isEnabled() is False


def test_generation_titlebar_tooltips_retranslate_existing_segments() -> None:
    """Keep tooltips and accessible names in the active language in place."""

    application = app()
    resource_root = Path(app_icon_module.__file__).resolve().parent / "i18n"
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert application.installTranslator(chinese)
    cluster = GenerationTitleBarActionCluster()
    try:
        assert [segment.toolTip() for segment in cluster._segments] == [
            "停止生成",
            "生成",
            "跳过当前生成",
            "生成队列",
        ]
        assert [segment.accessibleName() for segment in cluster._segments] == [
            "停止生成",
            "生成",
            "跳过当前生成",
            "生成队列",
        ]

        assert application.removeTranslator(chinese)
        assert application.installTranslator(japanese)
        for segment in cluster._segments:
            application.sendEvent(segment, QEvent(QEvent.Type.LanguageChange))

        assert [segment.toolTip() for segment in cluster._segments] == [
            "生成を停止",
            "生成",
            "生成をスキップ",
            "生成キュー",
        ]
        assert [segment.accessibleName() for segment in cluster._segments] == [
            "生成を停止",
            "生成",
            "生成をスキップ",
            "生成キュー",
        ]
    finally:
        application.removeTranslator(japanese)
        application.removeTranslator(chinese)
        cluster.close()


def test_generation_titlebar_segments_install_qfluent_tooltip_filters() -> None:
    """Each titlebar action segment should use the shared QFluent tooltip path."""

    app()
    cluster = GenerationTitleBarActionCluster()
    event = QEvent(QEvent.Type.ToolTip)

    for segment in cluster._segments:
        assert isinstance(segment._tooltip_filter, FluentToolTipFilter)
        assert segment._tooltip_filter.parent() is segment
        assert segment._tooltip_filter._show_when_disabled is True
        assert segment._tooltip_filter.eventFilter(segment, event) is True


def test_generation_titlebar_cluster_orders_segments_by_action_flow() -> None:
    """The destructive stop action should render before forward-flow actions."""

    app()
    cluster = GenerationTitleBarActionCluster()

    assert cluster.segment_roles == ("stop", "play", "skip", "queue")
    assert cluster._segments == (
        cluster.stopButton,
        cluster.playButton,
        cluster.skipButton,
        cluster.queueButton,
    )


def test_generation_titlebar_cluster_assigns_edges_from_segment_order() -> None:
    """Rounded edge ownership should follow position instead of segment role."""

    app()
    cluster = GenerationTitleBarActionCluster()

    assert cluster.stopButton._edge == "first"
    assert cluster.playButton._edge == "middle"
    assert cast(str, cluster.skipButton._edge) == "middle"
    assert cluster.queueButton._edge == "last"
