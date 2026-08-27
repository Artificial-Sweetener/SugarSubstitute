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

"""Verify prompt reorder widget painting contracts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar, cast

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPaintEvent
from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

import substitute.presentation.editor.prompt_editor.overlays.reorder_view as reorder_view_module
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_painter import (
    PromptChipPainter,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_state import (
    PromptReorderLandingPreviewPaintState,
    PromptReorderMarkerPaintState,
    PromptReorderViewRenderInput,
    PromptReorderViewRenderState,
    prompt_reorder_view_render_state,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_view import (
    PromptReorderView,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
)

from .support import (
    _style,
    _visual,
    _projection_snapshot,
)


def test_reorder_view_is_editor_backed_overlay_paint_surface() -> None:
    """Reorder animation keeps parent text visible below transparent chrome."""

    if QApplication.instance() is None:
        QApplication([])
    view = PromptReorderView()

    assert not view.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert view.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert view.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not view.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert view.mask().isEmpty()


def test_reorder_view_paint_clips_to_owned_region_without_background_fill(
    monkeypatch: MonkeyPatch,
) -> None:
    """Painting should draw only owned chrome instead of filling row rectangles."""

    class _FakeRenderHint:
        """Expose the painter render hints used by the view."""

        Antialiasing = "antialiasing"

    class _FakePainter:
        """Record reorder view painter calls without touching the window system."""

        RenderHint = _FakeRenderHint
        instances: ClassVar[list["_FakePainter"]] = []

        def __init__(self, widget: object) -> None:
            """Record the widget being painted."""

            self.widget = widget
            self.calls: list[tuple[str, object, object | None]] = []
            _FakePainter.instances.append(self)

        def setClipRegion(self, region: object) -> None:
            """Record paint clipping."""

            self.calls.append(("setClipRegion", region, None))

        def setRenderHint(self, hint: object, enabled: bool) -> None:
            """Record render hint changes."""

            self.calls.append(("setRenderHint", hint, enabled))

        def setBrush(self, brush: object) -> None:
            """Record brush changes."""

            self.calls.append(("setBrush", brush, None))

        def setPen(self, pen: object) -> None:
            """Record pen changes."""

            self.calls.append(("setPen", pen, None))

        def drawRoundedRect(
            self,
            rect: object,
            x_radius: object,
            y_radius: object,
        ) -> None:
            """Record rounded rect drawing."""

            self.calls.append(("drawRoundedRect", rect, (x_radius, y_radius)))

        def end(self) -> None:
            """Record painter shutdown."""

            self.calls.append(("end", None, None))

    class _FakeRegion:
        """Provide the paint event region consumed by the view."""

        def boundingRect(self) -> QRect:
            """Return a deterministic dirty rect."""

            return QRect(0, 0, 24, 16)

    class _FakePaintEvent:
        """Provide the QPaintEvent subset consumed by the view."""

        def region(self) -> _FakeRegion:
            """Return the deterministic fake region."""

            return _FakeRegion()

    if QApplication.instance() is None:
        QApplication([])
    view = PromptReorderView()
    view.resize(32, 20)
    view.set_render_state(
        PromptReorderViewRenderState(
            marker=PromptReorderMarkerPaintState(
                rect=QRectF(4.0, 5.0, 8.0, 9.0),
                color=QColor(255, 0, 0),
            )
        )
    )
    assert view.mask().isEmpty()
    monkeypatch.setattr(reorder_view_module, "QPainter", _FakePainter)

    view.paintEvent(cast(QPaintEvent, _FakePaintEvent()))

    calls = _FakePainter.instances[0].calls
    call_names = [call[0] for call in calls]
    assert calls[0][0] == "setClipRegion"
    assert calls[1] == ("setRenderHint", "antialiasing", True)
    assert "fillRect" not in call_names
    assert "setCompositionMode" not in call_names


def test_reorder_view_paints_complete_snapshot_before_raster_is_ready(
    monkeypatch: MonkeyPatch,
) -> None:
    """Deferred raster warming should preserve complete chip paint immediately."""

    class _FakeRenderHint:
        """Expose the painter render hint used by the view."""

        Antialiasing = "antialiasing"

    class _FakePainter:
        """Record snapshot translation without touching the window system."""

        RenderHint = _FakeRenderHint
        instances: ClassVar[list["_FakePainter"]] = []

        def __init__(self, widget: object) -> None:
            """Record the painter target."""

            self.widget = widget
            self.calls: list[tuple[str, object | None, object | None]] = []
            _FakePainter.instances.append(self)

        def setClipRegion(self, region: object) -> None:
            """Record paint clipping."""

            self.calls.append(("setClipRegion", region, None))

        def setRenderHint(self, hint: object, enabled: bool) -> None:
            """Record render hint changes."""

            self.calls.append(("setRenderHint", hint, enabled))

        def save(self) -> None:
            """Record painter state preservation."""

            self.calls.append(("save", None, None))

        def translate(self, dx: float, dy: float) -> None:
            """Record snapshot translation."""

            self.calls.append(("translate", dx, dy))

        def restore(self) -> None:
            """Record painter state restoration."""

            self.calls.append(("restore", None, None))

        def end(self) -> None:
            """Record painter shutdown."""

            self.calls.append(("end", None, None))

    class _FakeRegion:
        """Provide the paint event region consumed by the view."""

        def boundingRect(self) -> QRect:
            """Return a deterministic dirty rect."""

            return QRect(0, 0, 160, 32)

    class _FakePaintEvent:
        """Provide the paint event subset consumed by the view."""

        def region(self) -> _FakeRegion:
            """Return the deterministic fake region."""

            return _FakeRegion()

    if QApplication.instance() is None:
        QApplication([])
    visual = _visual(80.0)
    visual_snapshot = PromptReorderChipVisualSnapshot(
        segment_index=0,
        visual=visual,
        projection_snapshot=_projection_snapshot(0),
    )
    state = prompt_reorder_view_render_state(
        PromptReorderViewRenderInput(
            visual_style=_style(),
            preview_active=False,
            live_ordered_segment_indices=(0,),
            preview_ordered_segment_indices=(),
            live_geometries_by_index={},
            preview_geometries_by_index={},
            live_visuals_by_index={0: visual},
            preview_visuals_by_index={},
            dragged_segment_index=None,
            hovered_segment_index=None,
            active_segment_index=None,
            live_visual_snapshots_by_index={0: visual_snapshot},
        )
    )
    view = PromptReorderView()
    view.resize(180, 40)
    view.set_render_state(state)
    chrome_calls: list[PromptChipVisual] = []
    projection_calls: list[PromptReorderProjectionPaintSnapshot] = []
    monkeypatch.setattr(reorder_view_module, "QPainter", _FakePainter)
    monkeypatch.setattr(
        PromptChipPainter,
        "paint_chrome",
        lambda self, *, painter, visual, style: chrome_calls.append(visual),
    )
    monkeypatch.setattr(
        reorder_view_module,
        "paint_reorder_projection_snapshot",
        lambda painter, snapshot: projection_calls.append(snapshot),
    )

    view.paintEvent(cast(QPaintEvent, _FakePaintEvent()))

    assert chrome_calls == [visual]
    assert projection_calls == [visual_snapshot.projection_snapshot]
    call_names = [call[0] for call in _FakePainter.instances[0].calls]
    assert call_names[-4:] == ["save", "translate", "restore", "end"]


def test_reorder_view_paints_prepared_landing_shadow(
    monkeypatch: MonkeyPatch,
) -> None:
    """A published visual-backed landing shadow should reach the paint adapter."""

    visual = _visual(120.0)
    landing_preview = PromptReorderLandingPreviewPaintState(
        style=_style().outline_style(opacity=0.5, outline_width=1.0),
        visual=visual,
    )
    painted: list[PromptChipVisual] = []
    monkeypatch.setattr(
        PromptChipPainter,
        "paint_chrome",
        lambda self, *, painter, visual, style: painted.append(visual),
    )

    paint_host = cast(
        PromptReorderView,
        SimpleNamespace(_chip_painter=PromptChipPainter()),
    )
    PromptReorderView._paint_landing_preview(
        paint_host,
        cast(Any, object()),
        landing_preview,
    )

    assert painted == [visual]
