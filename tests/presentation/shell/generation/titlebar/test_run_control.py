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

"""Test generation titlebar run-control projection."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.presentation.shell.titlebar_buttons import (
    GenerationTitleBarRunControl,
)
from substitute.presentation.resources.app_icon import AppIcon
import substitute.presentation.shell.titlebar_buttons as titlebar_buttons

from tests.presentation.shell.generation.titlebar.support import app, presentation


def test_generation_titlebar_run_control_hides_batch_outside_generate_mode() -> None:
    """Run wrapper should expose batch count only in normal generate mode."""

    app()
    control = GenerationTitleBarRunControl()

    control.set_batch_count(4)
    assert control.batch_count() == 4
    assert control.effective_batch_count() == 4
    assert control._batch_accessory.isHidden() is False

    control.apply_generation_presentation(
        presentation(
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
        presentation(
            play_mode="end_continuous",
            play_tooltip="Stop continuous after current job",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
            mode_menu_enabled=False,
        )
    )
    assert control._batch_accessory.isHidden() is True
    assert control.effective_batch_count() == 1

    control.apply_generation_presentation(presentation(play_mode="generate"))
    assert control._batch_accessory.isHidden() is False
    assert control.effective_batch_count() == 4
    assert control.queue_button_target() is control.queueButton


def test_generation_titlebar_run_control_progress_stop_target_tracks_batch() -> None:
    """Progress strips should stop at batch input when it is visible."""

    app()
    control = GenerationTitleBarRunControl()

    assert control.progress_strip_stop_target() is control._batch_accessory

    control.apply_generation_presentation(
        presentation(
            play_mode="continuous",
            play_tooltip="Continuous",
            batch_accessory_visible=False,
            batch_accessory_enabled=False,
        )
    )

    assert control.progress_strip_stop_target() is control._action_cluster


def test_generation_titlebar_run_control_applies_generatepresentation() -> None:
    """Run wrapper should render normal generation from one presentation snapshot."""

    app()
    control = GenerationTitleBarRunControl()
    control.set_batch_count(3)

    control.apply_generation_presentation(presentation(play_mode="generate"))

    assert control.playButton.toolTip() == "Generate"
    assert control.playButton.accessibleName() == "Generate"
    assert control.playButton._icon is FIF.PLAY_SOLID
    assert control.playButton.isEnabled() is True
    assert control._batch_accessory.isHidden() is False
    assert control._batch_accessory.isEnabled() is True
    assert control.effective_batch_count() == 3


def test_generation_titlebar_run_control_applies_continuouspresentation() -> None:
    """Run wrapper should render inactive continuous mode without batch controls."""

    app()
    control = GenerationTitleBarRunControl()
    control.set_batch_count(5)

    control.apply_generation_presentation(
        presentation(
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


def test_generation_titlebar_run_control_applies_end_continuouspresentation() -> None:
    """Active continuous mode should use pause icon with explicit end-loop text."""

    app()
    control = GenerationTitleBarRunControl()

    control.apply_generation_presentation(
        presentation(
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

    app()
    control = GenerationTitleBarRunControl()
    queue_calls: list[bool] = []
    context_calls: list[bool] = []
    control.queueClicked.connect(lambda: queue_calls.append(True))
    control.queueContextMenuRequested.connect(lambda: context_calls.append(True))

    control.apply_generation_presentation(
        presentation(queue_primary_enabled=False, queue_badge_count=2)
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

    app()
    control = GenerationTitleBarRunControl()

    control.apply_generation_presentation(
        presentation(queue_segment_visible=False, queue_primary_enabled=True)
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
        presentation(queue_segment_visible=True, queue_primary_enabled=True)
    )

    assert control.queueButton.isHidden() is False
    assert cast(str, control.skipButton._edge) == "middle"
    assert control.queueButton._edge == "last"


def test_generation_titlebar_run_control_overlaps_tray_without_reordering_segments() -> (
    None
):
    """Batch tray should sit under the cluster while stop keeps first-edge ownership."""

    app()
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

    app()
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
