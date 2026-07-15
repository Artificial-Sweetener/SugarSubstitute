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

"""Tests for Qt-backed prompt projection surface layout behavior."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection.line_layout import (
    tag_keep_source_ranges_for_layout,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _projection_line_texts(surface: PromptProjectionSurface) -> tuple[str, ...]:
    """Return visible text grouped by projection visual line."""

    snapshot = cast(Any, surface)._layout._snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )


def test_projection_layout_keeps_short_tag_without_trailing_space_width() -> None:
    """Trailing separator space should not decide whether a short tag is kept."""

    source_text = (
        "test test test, test test test test test, "
        "test test test, test test test, test,"
    )
    document_view = PromptDocumentView(
        source_text=source_text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        has_trailing_comma=True,
    )

    assert (0, len("test test test,")) in tag_keep_source_ranges_for_layout(
        document_view
    )

    app = ensure_qapp()
    created_widgets: list[QWidget] = []
    box = show_prompt_editor(
        created_widgets,
        text=source_text,
        width=240,
    )
    try:
        surface = surface_for(box)
        surface._document_view = document_view  # noqa: SLF001
        surface._render_plan = PromptSyntaxRenderPlan(  # noqa: SLF001
            syntax_spans=(),
            renderer_views=(),
        )
        box.setGeometry(20, 20, 240, box.height())
        process_events(app)
        surface._rebuild_projection()  # noqa: SLF001

        line_texts = _projection_line_texts(surface)
        snapshot = cast(Any, surface)._layout._snapshot

        assert "test test test," in "\n".join(line_texts)
        for range_start, range_end in tag_keep_source_ranges_for_layout(document_view):
            owning_lines = tuple(
                line
                for line in snapshot.lines
                if line.source_content_start < range_end
                and range_start < line.source_content_end
            )
            assert len(owning_lines) == 1
    finally:
        for widget in reversed(created_widgets):
            widget.close()
            widget.deleteLater()
        process_events(app)
