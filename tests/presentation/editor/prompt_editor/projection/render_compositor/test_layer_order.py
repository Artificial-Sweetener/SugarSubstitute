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

"""Verify prompt projection compositor layer ordering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.projection.caret_renderer import (
    PromptCaretRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.diagnostic_renderer import (
    PromptDiagnosticRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.input_method_renderer import (
    PromptInputMethodRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.paint_cache import (
    PromptProjectionPaintCache,
)
from substitute.presentation.editor.prompt_editor.projection.region_chrome_renderer import (
    PromptRegionChromeRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.search_highlight_renderer import (
    PromptSearchHighlightRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.source_line_renderer import (
    PromptSourceLineChromeRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_renderer import (
    PromptTransientEditRenderer,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)


def test_render_compositor_owns_one_deterministic_live_layer_order(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every prepared live layer must draw in the declared z-order."""

    box = show_prompt_editor(widgets, text="alpha beta", width=360)
    surface = surface_for(box)
    calls: list[str] = []

    def recorder(name: str) -> Callable[..., None]:
        """Return one method replacement that records its layer."""

        def record(*args: object, **kwargs: object) -> None:
            del args, kwargs
            calls.append(name)

        return record

    def record_content(*args: object, **kwargs: object) -> str:
        """Record projection content and return one valid cache result."""

        del args, kwargs
        calls.append("content")
        return "hit"

    monkeypatch.setattr(PromptSourceLineChromeRenderer, "draw", recorder("source"))
    monkeypatch.setattr(PromptRegionChromeRenderer, "draw", recorder("region"))
    monkeypatch.setattr(PromptSearchHighlightRenderer, "draw", recorder("search"))
    monkeypatch.setattr(
        PromptProjectionPaintCache,
        "paint_projection_content",
        record_content,
    )
    monkeypatch.setattr(
        PromptTransientEditRenderer,
        "draw_insertion",
        recorder("insertion"),
    )
    monkeypatch.setattr(PromptDiagnosticRenderer, "draw", recorder("diagnostics"))
    monkeypatch.setattr(
        PromptTransientEditRenderer,
        "draw_deletion",
        recorder("deletion"),
    )
    monkeypatch.setattr(PromptInputMethodRenderer, "draw", recorder("ime"))
    monkeypatch.setattr(PromptCaretRenderer, "draw", recorder("caret"))
    pixmap = QPixmap(surface.viewport().size())
    painter = QPainter(pixmap)
    try:
        result = cast(Any, surface)._render_compositor.draw(
            painter,
            cast(Any, surface)._render_frame_owner.frame,
            event_clip=QRectF(surface.viewport().rect()),
        )
    finally:
        painter.end()

    assert result == "hit"
    assert calls == [
        "source",
        "region",
        "search",
        "content",
        "insertion",
        "diagnostics",
        "deletion",
        "ime",
        "caret",
    ]
