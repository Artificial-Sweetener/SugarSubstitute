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

"""Guard immutable render-frame publication and deterministic composition."""

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
from tests.prompt_projection_surface_test_helpers import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
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


def test_surface_paint_reads_only_event_clip_and_published_render_frame(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paint must not republish layers or discover mutable feature state."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha beta", width=360)
    surface = surface_for(box)
    process_events(app)

    def reject_discovery(*args: object, **kwargs: object) -> None:
        """Reject any render-frame preparation reached from paint."""

        del args, kwargs
        raise AssertionError("paint discovered mutable prompt state")

    for method_name in (
        "_publish_render_frame",
        "_should_paint_caret",
        "_preview_visible_region",
        "_fresh_reorder_surface_chrome",
    ):
        monkeypatch.setattr(surface, method_name, reject_discovery)

    image = render_surface_viewport(surface)

    assert not image.isNull()


def test_unchanged_render_publication_reuses_the_exact_frame(
    widgets: list[QWidget],
) -> None:
    """An unchanged publication should allocate no replacement render frame."""

    box = show_prompt_editor(widgets, text="alpha beta", width=360)
    surface = surface_for(box)
    owner = cast(Any, surface)._render_frame_owner
    initial_frame = owner.frame

    cast(Any, surface)._publish_render_frame()
    first_repeat = owner.frame
    cast(Any, surface)._publish_render_frame()

    assert first_repeat is initial_frame
    assert owner.frame is initial_frame
