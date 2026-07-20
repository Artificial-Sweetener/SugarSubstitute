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

"""Contract tests for the titlebar segmented generation action cluster."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QEvent, QTranslator, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButtonState,
)
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
import pytest

from substitute.presentation.shell.titlebar_buttons import (
    GenerationClusterRevealHost,
    GenerationBatchCountAccessory,
    GenerationTitleBarActionCluster,
    GenerationTitleBarRunControl,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationPlayPresentationMode,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
)
import substitute.presentation.shell.chrome_style as chrome_style
import substitute.presentation.shell.titlebar_buttons as titlebar_buttons
from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    winui_accent_button_disabled_fill_color,
    winui_accent_button_disabled_foreground_color,
    workflow_chrome_wash_color,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "titlebar Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by titlebar cluster tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_generation_titlebar_cluster_emits_segment_intents() -> None:
    """Left-clicking each segment should emit its command intent."""

    _app()
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


def test_generation_batch_count_accessory_clamps_and_emits_changes() -> None:
    """Batch accessory should keep a positive count and report real changes."""

    _app()
    accessory = GenerationBatchCountAccessory()
    changes: list[int] = []
    accessory.valueChanged.connect(lambda value: changes.append(value))

    assert accessory.batch_count() == 1
    assert accessory.down_chevron_enabled() is False

    accessory.set_batch_count(0)
    assert accessory.batch_count() == 1
    assert changes == []

    accessory.increment()
    assert accessory.batch_count() == 2
    assert accessory.down_chevron_enabled() is True

    accessory.decrement()
    accessory.decrement()

    assert accessory.batch_count() == 1
    assert accessory.down_chevron_enabled() is False
    assert changes == [2, 1]


def test_generation_batch_count_accessory_chevron_clicks_adjust_value() -> None:
    """Chevron hit zones should increment and decrement the batch value."""

    _app()
    accessory = GenerationBatchCountAccessory()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("up").center().toPoint(),
    )
    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("down").center().toPoint(),
    )
    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._role_rect("down").center().toPoint(),
    )

    assert accessory.batch_count() == 1


def test_generation_batch_count_accessory_uses_body_material_wash() -> None:
    """Batch accessory should use the window wash instead of accent fill."""

    _app()
    accessory = GenerationBatchCountAccessory()

    assert accessory._surface_color() == QColor(*body_material_wash_color(None))


def test_generation_batch_count_accessory_accepts_manual_number_entry() -> None:
    """Clicking the value region should allow direct numeric entry."""

    _app()
    accessory = GenerationBatchCountAccessory()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._value_rect().center().toPoint(),
    )
    accessory._editor.clear()
    QTest.keyClicks(accessory._editor, "777")
    QTest.keyClick(accessory._editor, Qt.Key.Key_Return)

    assert accessory.batch_count() == 777
    assert accessory._editor.isHidden() is True


def test_generation_batch_count_accessory_commits_manual_entry_on_outside_click() -> (
    None
):
    """Clicking outside the spinner should commit typed text and close editing."""

    _app()
    container = QWidget()
    accessory = GenerationBatchCountAccessory(container)
    outside = QWidget(container)
    accessory.setGeometry(0, 0, accessory.width(), accessory.height())
    outside.setGeometry(accessory.width() + 20, 0, 40, accessory.height())
    outside.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    container.show()

    QTest.mouseClick(
        accessory,
        Qt.MouseButton.LeftButton,
        pos=accessory._value_rect().center().toPoint(),
    )
    accessory._editor.clear()
    QTest.keyClicks(accessory._editor, "42")
    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)

    assert accessory.batch_count() == 42
    assert accessory._editor.isHidden() is True
    assert not accessory._editor.hasFocus()
    container.close()


def test_generation_batch_count_accessory_centers_three_digit_value_region() -> None:
    """The value region should leave centered room for three digits."""

    _app()
    accessory = GenerationBatchCountAccessory()

    assert accessory._value_width() >= 44
    assert accessory._value_rect().center().x() < accessory._role_rect("up").left()
    assert accessory._editor.validator() is not None


def test_generation_titlebar_run_control_hides_batch_outside_generate_mode() -> None:
    """Run wrapper should expose batch count only in normal generate mode."""

    _app()
    control = GenerationTitleBarRunControl()

    control.set_batch_count(4)
    assert control.batch_count() == 4
    assert control.effective_batch_count() == 4
    assert control._batch_accessory.isHidden() is False

    control.apply_generation_presentation(
        _presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )
    assert control._batch_accessory.isHidden() is True
    assert control.effective_batch_count() == 1
    assert control.width() == control._action_cluster.width()

    control.apply_generation_presentation(
        _presentation(
            play_mode="end_continuous",
            play_tooltip="Stop continuous after current job",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )
    assert control._batch_accessory.isHidden() is True
    assert control.effective_batch_count() == 1

    control.apply_generation_presentation(_presentation(play_mode="generate"))
    assert control._batch_accessory.isHidden() is False
    assert control.effective_batch_count() == 4
    assert control.queue_button_target() is control.queueButton


def test_generation_titlebar_run_control_progress_stop_target_tracks_batch() -> None:
    """Progress strips should stop at batch input when it is visible."""

    _app()
    control = GenerationTitleBarRunControl()

    assert control.progress_strip_stop_target() is control._batch_accessory

    control.apply_generation_presentation(
        _presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )

    assert control.progress_strip_stop_target() is control._action_cluster


def test_generation_titlebar_run_control_applies_generate_presentation() -> None:
    """Run wrapper should render normal generation from one presentation snapshot."""

    _app()
    control = GenerationTitleBarRunControl()
    control.set_batch_count(3)

    control.apply_generation_presentation(_presentation(play_mode="generate"))

    assert control.playButton.toolTip() == "Generate"
    assert control.playButton.accessibleName() == "Generate"
    assert control.playButton._icon is FIF.PLAY_SOLID
    assert control.playButton.isEnabled() is True
    assert control._batch_accessory.isHidden() is False
    assert control._batch_accessory.isEnabled() is True
    assert control.effective_batch_count() == 3


def test_generation_titlebar_run_control_applies_continuous_presentation() -> None:
    """Run wrapper should render inactive continuous mode without batch controls."""

    _app()
    control = GenerationTitleBarRunControl()
    control.set_batch_count(5)

    control.apply_generation_presentation(
        _presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )

    assert control.playButton.toolTip() == "Continuous"
    assert control.playButton.accessibleName() == "Continuous"
    assert control.playButton._icon is AppIcon.INFINITY_HIGH_CONTRAST
    assert control._batch_accessory.isHidden() is True
    assert control.effective_batch_count() == 1


def test_generation_titlebar_run_control_applies_end_continuous_presentation() -> None:
    """Active continuous mode should use pause icon with explicit end-loop text."""

    _app()
    control = GenerationTitleBarRunControl()

    control.apply_generation_presentation(
        _presentation(
            play_mode="end_continuous",
            play_tooltip="Stop continuous after current job",
            stop_enabled=True,
            skip_enabled=True,
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )

    assert control.playButton.toolTip() == "Stop continuous after current job"
    assert control.playButton.accessibleName() == "Stop continuous after current job"
    assert control.playButton._icon is FIF.PAUSE_BOLD
    assert control.stopButton.isEnabled() is True
    assert control.skipButton.isEnabled() is True
    assert control._action_cluster._action_generate.isEnabled() is False
    assert control._action_cluster._action_continuous.isEnabled() is False


def test_generation_titlebar_run_control_preserves_queue_context_surface() -> None:
    """Presentation-disabled queue primary action should keep context access alive."""

    _app()
    control = GenerationTitleBarRunControl()
    queue_calls: list[bool] = []
    context_calls: list[bool] = []
    control.queueClicked.connect(lambda: queue_calls.append(True))
    control.queueContextMenuRequested.connect(lambda: context_calls.append(True))

    control.apply_generation_presentation(
        _presentation(queue_primary_enabled=False, queue_badge_count=2)
    )

    QTest.mouseClick(control.queueButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(control.queueButton, Qt.MouseButton.RightButton)

    assert control.queueButton.isEnabled() is True
    assert control.queueButton.primary_action_enabled() is False
    assert control.queueButton.badge_count() == 2
    assert queue_calls == []
    assert context_calls == [True]


def test_generation_titlebar_run_control_applies_queue_segment_visibility() -> None:
    """Presentation should hide and restore queue geometry through one snapshot."""

    _app()
    control = GenerationTitleBarRunControl()

    control.apply_generation_presentation(
        _presentation(queue_segment_visible=False, queue_primary_enabled=True)
    )

    assert control.queueButton.isHidden() is True
    assert tuple(
        segment.role for segment in control._action_cluster._visible_segments()
    ) == (
        "stop",
        "play",
        "skip",
    )
    assert cast(str, control.skipButton._edge) == "last"

    control.apply_generation_presentation(
        _presentation(queue_segment_visible=True, queue_primary_enabled=True)
    )

    assert control.queueButton.isHidden() is False
    assert cast(str, control.skipButton._edge) == "middle"
    assert control.queueButton._edge == "last"


def test_generation_titlebar_run_control_overlaps_tray_without_reordering_segments() -> (
    None
):
    """Batch tray should sit under the cluster while stop keeps first-edge ownership."""

    _app()
    control = GenerationTitleBarRunControl()

    assert control.stopButton._edge == "first"
    assert control._action_cluster.x() == (
        titlebar_buttons._BATCH_ACCESSORY_WIDTH
        - titlebar_buttons._BATCH_CLUSTER_OVERLAP
    )
    assert (
        control._batch_accessory._role_rect("up").right() < control._action_cluster.x()
    )
    assert titlebar_buttons._BATCH_CHEVRON_WIDTH <= 14
    assert titlebar_buttons._BATCH_CHEVRON_STROKE < 1.2
    assert control._batch_accessory.x() == 0
    assert control.width() == (
        control._action_cluster.width()
        + titlebar_buttons._BATCH_ACCESSORY_WIDTH
        - titlebar_buttons._BATCH_CLUSTER_OVERLAP
    )


def test_generation_titlebar_run_control_proxies_action_signals() -> None:
    """Run wrapper should preserve the action-cluster signal surface."""

    _app()
    control = GenerationTitleBarRunControl()
    play_calls: list[bool] = []
    skip_calls: list[bool] = []
    queue_calls: list[bool] = []
    stop_calls: list[bool] = []
    control.playClicked.connect(lambda: play_calls.append(True))
    control.skipClicked.connect(lambda: skip_calls.append(True))
    control.queueClicked.connect(lambda: queue_calls.append(True))
    control.stopClicked.connect(lambda: stop_calls.append(True))

    QTest.mouseClick(control.playButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(control.skipButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(control.queueButton, Qt.MouseButton.LeftButton)
    QTest.mouseClick(control.stopButton, Qt.MouseButton.LeftButton)

    assert play_calls == [True]
    assert skip_calls == [True]
    assert queue_calls == [True]
    assert stop_calls == [True]


def test_generation_titlebar_play_right_click_requests_mode_menu_only() -> None:
    """Right-clicking play should not emit the normal play command."""

    _app()
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

    _app()
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

    _app()
    cluster = GenerationTitleBarActionCluster()
    queue_calls: list[bool] = []
    context_calls: list[bool] = []
    cluster.queueClicked.connect(lambda: queue_calls.append(True))
    cluster.queueContextMenuRequested.connect(lambda: context_calls.append(True))
    cluster.apply_generation_presentation(
        _presentation(
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

    _app()
    cluster = GenerationTitleBarActionCluster()
    selected_modes: list[str] = []
    cluster.generateModeSelected.connect(lambda mode: selected_modes.append(mode))

    cluster._action_generate.trigger()
    cluster._action_continuous.trigger()

    assert selected_modes == ["generate", "continuous"]
    assert not hasattr(cluster, "_action_scenes")


def test_generation_titlebar_cluster_applies_presentation_state() -> None:
    """The cluster should expose projected tooltips and action availability."""

    _app()
    cluster = GenerationTitleBarActionCluster()
    play_tooltip_filter = cluster.playButton._tooltip_filter

    cluster.apply_generation_presentation(_presentation(play_mode="generate"))
    assert cluster.playButton.toolTip() == "Generate"
    assert cluster.playButton._tooltip_filter is play_tooltip_filter

    cluster.apply_generation_presentation(
        _presentation(
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
        _presentation(
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
        _presentation(
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
        _presentation(
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
        _presentation(
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

    application = _app()
    resource_root = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
    )
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

    _app()
    cluster = GenerationTitleBarActionCluster()
    event = QEvent(QEvent.Type.ToolTip)

    for segment in cluster._segments:
        assert isinstance(segment._tooltip_filter, FluentToolTipFilter)
        assert segment._tooltip_filter.parent() is segment
        assert segment._tooltip_filter._show_when_disabled is True
        assert segment._tooltip_filter.eventFilter(segment, event) is True


def test_generation_titlebar_cluster_orders_segments_by_action_flow() -> None:
    """The destructive stop action should render before forward-flow actions."""

    _app()
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

    _app()
    cluster = GenerationTitleBarActionCluster()

    assert cluster.stopButton._edge == "first"
    assert cluster.playButton._edge == "middle"
    assert cast(str, cluster.skipButton._edge) == "middle"
    assert cluster.queueButton._edge == "last"


def test_generation_cluster_reveal_host_starts_collapsed() -> None:
    """Output-canvas reveal host should expose only the chevron by default."""

    _app()
    host = GenerationClusterRevealHost()

    assert host.is_expanded() is False
    assert host.control.isHidden() is True
    assert host.minimumWidth() == titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH
    assert host.maximumWidth() == titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH
    assert host.revealButton.toolTip() == "Show generation controls"
    assert host.revealButton.accessibleName() == "Show generation controls"
    assert host.revealButton.width() == 46
    assert host.revealButton.height() == 32


def test_generation_cluster_reveal_host_toggles_without_animation() -> None:
    """Reveal host should expand and collapse the contained run control."""

    _app()
    host = GenerationClusterRevealHost()
    expanded_width = (
        titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH + host.control.width()
    )

    host.set_expanded(True, animated=False)

    assert host.is_expanded() is True
    assert host.control.isHidden() is False
    assert host.minimumWidth() == expanded_width
    assert host.maximumWidth() == expanded_width
    assert host.revealButton.toolTip() == "Hide generation controls"

    host.set_expanded(False, animated=False)

    assert host.is_expanded() is False
    assert host.control.isHidden() is True
    assert host.minimumWidth() == titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH
    assert host.maximumWidth() == titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH


def test_generation_cluster_reveal_host_emits_expanded_changes() -> None:
    """Reveal host should notify dependent views when expanded state changes."""

    _app()
    host = GenerationClusterRevealHost()
    changes: list[bool] = []
    host.expandedChanged.connect(changes.append)

    host.set_expanded(True, animated=False)
    host.set_expanded(True, animated=False)
    host.set_expanded(False, animated=False)

    assert changes == [True, False]


def test_generation_reveal_button_uses_qfluent_titlebar_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reveal button should receive qfluent's theme-aware titlebar stylesheet."""

    _app()
    applied: list[object] = []
    monkeypatch.setattr(
        titlebar_buttons,
        "FluentStyleSheet",
        SimpleNamespace(FLUENT_WINDOW=SimpleNamespace(apply=applied.append)),
    )
    button = titlebar_buttons.GenerationClusterRevealButton()

    assert applied == [button]
    assert button.width() == 46
    assert button.height() == 32
    assert titlebar_buttons._GENERATION_REVEAL_CHEVRON_HALF_WIDTH < 3.0
    assert titlebar_buttons._GENERATION_REVEAL_CHEVRON_HALF_HEIGHT < 4.5


def test_generation_cluster_reveal_host_uses_accordion_motion_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Animated reveal should use centralized accordion motion policy."""

    _app()
    monkeypatch.setattr(titlebar_buttons, "is_reduced_motion_enabled", lambda: False)
    host = GenerationClusterRevealHost()

    host.set_expanded(True)
    assert host._reveal_animation.duration() == ACCORDION_EXPAND_DURATION_MS
    assert host._reveal_animation.easingCurve() == ACCORDION_EXPAND_EASING_CURVE
    host._reveal_animation.stop()

    host.set_expanded(False)
    assert host._reveal_animation.duration() == ACCORDION_COLLAPSE_DURATION_MS
    assert host._reveal_animation.easingCurve() == ACCORDION_COLLAPSE_EASING_CURVE
    host._reveal_animation.stop()


def test_generation_cluster_reveal_host_reduced_motion_jumps_to_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reduced motion should skip animation and settle final width immediately."""

    _app()
    monkeypatch.setattr(titlebar_buttons, "is_reduced_motion_enabled", lambda: True)
    host = GenerationClusterRevealHost()
    expanded_width = (
        titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH + host.control.width()
    )

    host.set_expanded(True)

    assert host.minimumWidth() == expanded_width
    assert host.maximumWidth() == expanded_width
    assert host.control.isHidden() is False


def test_generation_titlebar_queue_segment_can_hide_and_restore() -> None:
    """Queue segment visibility should update cluster geometry and edge ownership."""

    _app()
    cluster = GenerationTitleBarActionCluster()

    assert tuple(segment.role for segment in cluster._visible_segments()) == (
        "stop",
        "play",
        "skip",
        "queue",
    )
    assert cluster.width() == titlebar_buttons._SEGMENT_WIDTH * 4

    cluster.apply_generation_presentation(
        _presentation(queue_segment_visible=False, queue_primary_enabled=True)
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
        _presentation(queue_segment_visible=True, queue_primary_enabled=True)
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

    _app()
    cluster = GenerationTitleBarActionCluster()

    cluster.apply_generation_presentation(
        _presentation(
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
        _presentation(
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
        _presentation(
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

    _app()
    cluster = GenerationTitleBarActionCluster()
    monkeypatch.setattr(titlebar_buttons, "themeColor", lambda: QColor("#0078d4"))

    cluster.apply_generation_presentation(
        _presentation(queue_primary_enabled=True, queue_badge_count=12)
    )

    assert cluster.queueButton.badge_count() == 12
    assert cluster.queueButton.badge_text_color() == QColor("#0078d4")

    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: False)
    assert cluster.queueButton.badge_fill_color() == QColor("#ffffff")

    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)
    assert cluster.queueButton.badge_fill_color() == QColor("#000000")


def test_generation_titlebar_compensates_padded_icon_visual_rects() -> None:
    """Padded glyphs should use larger rects while standard FIF icons stay compact."""

    _app()
    cluster = GenerationTitleBarActionCluster()

    assert cluster.playButton._icon_rect().width() == 16.0
    cluster.apply_generation_presentation(
        _presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )
    assert cluster.playButton._icon_rect().width() == 24.0
    cluster.apply_generation_presentation(
        _presentation(
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

    _app()
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

    _app()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: False)
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: False)
    cluster = GenerationTitleBarActionCluster()
    cluster.apply_generation_presentation(
        _presentation(
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

    _app()
    monkeypatch.setattr(titlebar_buttons, "isDarkTheme", lambda: True)
    monkeypatch.setattr(chrome_style, "isDarkTheme", lambda: True)
    cluster = GenerationTitleBarActionCluster()
    cluster.apply_generation_presentation(
        _presentation(
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


def _presentation(
    *,
    play_mode: GenerationPlayPresentationMode = "generate",
    play_enabled: bool = True,
    play_tooltip: str = "Generate",
    stop_enabled: bool = False,
    skip_enabled: bool = False,
    queue_primary_enabled: bool = False,
    queue_badge_count: int = 0,
    queue_segment_visible: bool = True,
    batch_accessory_visible: bool = True,
    batch_accessory_enabled: bool = True,
    mode_menu_enabled: bool = True,
) -> GenerationActionPresentation:
    """Return one titlebar generation presentation for widget contract tests."""

    return GenerationActionPresentation(
        play_mode=play_mode,
        play_enabled=play_enabled,
        play_tooltip=play_tooltip,
        stop_enabled=stop_enabled,
        skip_enabled=skip_enabled,
        queue_primary_enabled=queue_primary_enabled,
        queue_badge_count=queue_badge_count,
        queue_segment_visible=queue_segment_visible,
        batch_accessory_visible=batch_accessory_visible,
        batch_accessory_enabled=batch_accessory_enabled,
        mode_menu_enabled=mode_menu_enabled,
    )


def test_generation_titlebar_cluster_uses_acrylic_specific_surface_and_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic clusters should keep the wash surface and accent-colored icons."""

    _app()
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
