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

"""Verify generic floating canvas snapshot and lifecycle contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from substitute.application.workspace_state import (
    FloatingCanvasWindowSnapshot,
    WindowGeometrySnapshot,
)
from substitute.presentation.canvas.host.floating_canvas_snapshot import (
    apply_restored_floating_snapshot,
    floating_canvas_snapshot,
)
from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)


def test_floating_snapshot_captures_geometry_and_display_state() -> None:
    """Generic floating snapshots should remain Qt-free and restorable."""

    window = SimpleNamespace(
        label="Output",
        geometry=lambda: SimpleNamespace(
            x=lambda: 10,
            y=lambda: 20,
            width=lambda: 640,
            height=lambda: 480,
        ),
        isFullScreen=lambda: False,
        isMaximized=lambda: True,
    )

    snapshot = floating_canvas_snapshot(window)

    assert snapshot == FloatingCanvasWindowSnapshot(
        label="Output",
        geometry=WindowGeometrySnapshot(x=10, y=20, width=640, height=480),
        window_display_state="maximized",
    )


def test_floating_snapshot_restore_applies_geometry_before_display_state() -> None:
    """Window placement should settle before the durable display mode is applied."""

    calls: list[tuple[object, ...]] = []
    window = SimpleNamespace(
        setGeometry=lambda *args: calls.append(("geometry", *args)),
        showFullScreen=lambda: calls.append(("fullscreen",)),
        showMaximized=lambda: calls.append(("maximized",)),
        showNormal=lambda: calls.append(("normal",)),
    )

    apply_restored_floating_snapshot(
        window,
        FloatingCanvasWindowSnapshot(
            label="Input",
            geometry=WindowGeometrySnapshot(x=10, y=20, width=640, height=480),
            window_display_state="fullscreen",
        ),
    )

    assert calls == [("geometry", 10, 20, 640, 480), ("fullscreen",)]


def test_floating_window_close_redocks_only_while_host_is_open() -> None:
    """Closing a live window should redock while host teardown should not."""

    redocked: list[tuple[object, str]] = []
    accepted: list[bool] = []
    canvas = SimpleNamespace(findChildren=lambda _type: [])
    open_window = cast(
        FloatingCanvasWindow,
        SimpleNamespace(
            _floating_chrome=None,
            canvas_widget=canvas,
            label="Input",
            redock_callback=lambda widget, label: redocked.append((widget, label)),
            parent=lambda: SimpleNamespace(closing=False),
        ),
    )
    closing_window = cast(
        FloatingCanvasWindow,
        SimpleNamespace(
            _floating_chrome=None,
            canvas_widget=canvas,
            label="Input",
            redock_callback=lambda widget, label: redocked.append((widget, label)),
            parent=lambda: SimpleNamespace(closing=True),
        ),
    )
    event = SimpleNamespace(accept=lambda: accepted.append(True))

    FloatingCanvasWindow.closeEvent(open_window, event)
    FloatingCanvasWindow.closeEvent(closing_window, event)

    assert redocked == [(canvas, "Input")]
    assert accepted == [True, True]


def test_floating_window_disposes_domain_chrome_before_redocking() -> None:
    """A floating window should release domain chrome before returning its canvas."""

    calls: list[str] = []
    chrome = SimpleNamespace(dispose=lambda _window: calls.append("dispose"))
    fake = cast(
        FloatingCanvasWindow,
        SimpleNamespace(
            _floating_chrome=chrome,
            canvas_widget=SimpleNamespace(findChildren=lambda _type: []),
            label="Output",
            redock_callback=lambda _widget, _label: calls.append("redock"),
            parent=lambda: SimpleNamespace(closing=False),
        ),
    )
    event = SimpleNamespace(accept=lambda: calls.append("accept"))

    FloatingCanvasWindow.closeEvent(fake, event)

    assert calls == ["dispose", "redock", "accept"]
