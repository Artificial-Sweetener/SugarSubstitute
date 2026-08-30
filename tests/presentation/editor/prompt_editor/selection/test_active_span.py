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

"""Verify active-span painting preserves projection geometry."""

from __future__ import annotations


import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.presentation.editor.prompt_editor.selection.support import (
    _set_cursor_position,
)


def test_projection_surface_set_active_span_does_not_rebuild_projection_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret-driven active-span changes should not rebuild the projection snapshot."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, (cat:1.05), omega",
        width=240,
    )
    surface = surface_for(box)
    _set_cursor_position(box, 0)
    process_events(app)

    rebuild_calls: list[str] = []
    monkeypatch.setattr(
        surface,
        "_rebuild_projection",
        lambda: rebuild_calls.append("rebuild"),
    )

    surface.set_active_span(
        PromptSyntaxSpanView(kind="emphasis", start=7, end=17, depth=0),
        cursor_position=10,
    )

    assert rebuild_calls == []
