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

"""Verify Output-owned floating canvas chrome contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.application.workspace_state import FloatingCanvasWindowSnapshot
from substitute.presentation.canvas.output.output_floating_chrome import (
    OutputFloatingChrome,
    OutputFloatingChromeFactory,
)
from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
)
from substitute.presentation.shell.generation_progress_strip_registry import (
    GenerationProgressStripRegistry,
)
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.titlebar_buttons import GenerationClusterRevealHost


def test_output_chrome_enriches_and_restores_reveal_state() -> None:
    """Output chrome should own its durable generation-control reveal state."""

    chrome = OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    reveal_calls: list[tuple[bool, bool]] = []
    chrome.generation_reveal_host = cast(
        GenerationClusterRevealHost,
        SimpleNamespace(
            is_expanded=lambda: True,
            set_expanded=lambda revealed, *, animated: reveal_calls.append(
                (revealed, animated)
            ),
        ),
    )

    captured = chrome.capture_snapshot(FloatingCanvasWindowSnapshot(label="Output"))
    chrome.restore_snapshot(
        FloatingCanvasWindowSnapshot(
            label="Output",
            output_generation_controls_revealed=False,
        )
    )

    assert captured.output_generation_controls_revealed is True
    assert reveal_calls == [(False, False)]


def test_output_chrome_factory_updates_live_and_future_instances() -> None:
    """Registry replacement should reach existing chrome and seed future chrome."""

    factory = OutputFloatingChromeFactory()
    existing = factory()
    titlebar_registry = cast(GenerationTitleBarControlRegistry, object())
    progress_registry = cast(GenerationProgressStripRegistry, object())

    factory.set_titlebar_control_registry(titlebar_registry)
    factory.set_progress_strip_registry(progress_registry)
    future = factory()

    assert existing._titlebar_control_registry is titlebar_registry
    assert existing._progress_strip_registry is progress_registry
    assert future._titlebar_control_registry is titlebar_registry
    assert future._progress_strip_registry is progress_registry


def test_output_chrome_dispose_unregisters_owned_controls() -> None:
    """Closing Output chrome should unregister both shared generation surfaces."""

    unregistered_titlebar: list[object] = []
    unregistered_progress: list[object] = []
    chrome = OutputFloatingChrome(
        titlebar_control_registry=cast(
            GenerationTitleBarControlRegistry,
            SimpleNamespace(unregister=unregistered_titlebar.append),
        ),
        progress_strip_registry=cast(
            GenerationProgressStripRegistry,
            SimpleNamespace(unregister=unregistered_progress.append),
        ),
    )
    control = object()
    strip = cast(GenerationProgressStrip, object())
    chrome.generation_reveal_host = cast(
        GenerationClusterRevealHost,
        SimpleNamespace(control=control),
    )
    chrome.generation_progress_strip = strip

    chrome.dispose(object())

    assert unregistered_titlebar == [control]
    assert unregistered_progress == [strip]


def test_output_progress_width_stops_before_revealed_titlebar_controls() -> None:
    """Floating progress chrome should not paint beneath generation controls."""

    chrome = OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    stop_target = SimpleNamespace(
        mapTo=lambda _window, _point: SimpleNamespace(x=lambda: 620)
    )
    chrome.generation_reveal_host = cast(
        GenerationClusterRevealHost,
        SimpleNamespace(
            control=SimpleNamespace(progress_strip_stop_target=lambda: stop_target)
        ),
    )

    assert chrome._overlay_width(SimpleNamespace(width=lambda: 800)) == 620


def test_output_progress_visibility_requires_revealed_controls() -> None:
    """The shared progress registry gate should follow local reveal state."""

    chrome = OutputFloatingChrome(
        titlebar_control_registry=None,
        progress_strip_registry=None,
    )
    chrome.generation_reveal_host = cast(
        GenerationClusterRevealHost,
        SimpleNamespace(is_expanded=lambda: False),
    )
    assert chrome._generation_progress_visible_gate() is False

    chrome.generation_reveal_host = cast(
        GenerationClusterRevealHost,
        SimpleNamespace(is_expanded=lambda: True),
    )
    assert chrome._generation_progress_visible_gate() is True
