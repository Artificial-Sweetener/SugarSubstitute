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

"""Test generation titlebar reveal-host behavior and motion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.presentation.shell.titlebar_buttons import (
    GenerationClusterRevealHost,
)
from substitute.presentation.motion import (
    ACCORDION_COLLAPSE_DURATION_MS,
    ACCORDION_COLLAPSE_EASING_CURVE,
    ACCORDION_EXPAND_DURATION_MS,
    ACCORDION_EXPAND_EASING_CURVE,
)
import substitute.presentation.shell.titlebar_buttons as titlebar_buttons

from tests.presentation.shell.generation.titlebar.support import app


def test_generation_cluster_reveal_host_starts_collapsed() -> None:
    """Output-canvas reveal host should expose only the chevron by default."""

    app()
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

    app()
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

    app()
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

    app()
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

    app()
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

    app()
    monkeypatch.setattr(titlebar_buttons, "is_reduced_motion_enabled", lambda: True)
    host = GenerationClusterRevealHost()
    expanded_width = (
        titlebar_buttons._GENERATION_REVEAL_BUTTON_WIDTH + host.control.width()
    )

    host.set_expanded(True)

    assert host.minimumWidth() == expanded_width
    assert host.maximumWidth() == expanded_width
    assert host.control.isHidden() is False
