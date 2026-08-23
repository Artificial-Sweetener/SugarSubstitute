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

"""Verify prompt reorder preview-projection cache identity."""

from __future__ import annotations

from dataclasses import replace

import pytest


from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.theme import (
    semantic_palette_from_theme,
)

from .support import (
    _service,
    _context,
    _changed_context,
    _counter,
    _build_reorder_preview_state,
)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("source_revision", 2),
        ("viewport_width", 481),
        ("preview_layout_key", ("layout", "changed")),
        ("base_drag_layout_key", ("base-layout", "changed")),
        ("active_drop_target_identity", ("line", 0, 2)),
    ],
)
def test_reorder_projection_service_cache_key_includes_rebuild_inputs(
    app: QApplication,
    field_name: str,
    field_value: object,
) -> None:
    """Projection cache identity should include source, viewport, layout, and target."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    base_context = _context()

    service.set_preview_state(
        preview_state,
        context=base_context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_context = service.counters()
    changed_context = _changed_context(base_context, field_name, field_value)
    service.set_preview_state(
        preview_state,
        context=changed_context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_context = service.counters()

    assert _counter(after_changed_context, "projection_snapshot_rebuild_count") > (
        _counter(before_changed_context, "projection_snapshot_rebuild_count")
    )


def test_reorder_projection_service_cache_key_includes_render_plan(
    app: QApplication,
) -> None:
    """Changing renderer-visible syntax inputs should rebuild preview projection."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    changed_preview_snapshot = replace(
        preview_state.preview_snapshot,
        render_plan=PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=()),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_render_plan = service.counters()
    service.set_preview_state(
        replace(preview_state, preview_snapshot=changed_preview_snapshot),
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_render_plan = service.counters()

    assert _counter(
        after_changed_render_plan,
        "projection_snapshot_rebuild_count",
    ) > _counter(before_changed_render_plan, "projection_snapshot_rebuild_count")


def test_reorder_projection_service_cache_key_includes_font(
    app: QApplication,
) -> None:
    """Changing layout font inputs should rebuild preview and base-drag layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    font = QFont()
    changed_font = QFont(font)
    changed_font.setPointSize(font.pointSize() + 3)

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=font,
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_changed_font = service.counters()
    service.set_preview_state(
        preview_state,
        context=_context(),
        font=changed_font,
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_changed_font = service.counters()

    assert _counter(after_changed_font, "projection_snapshot_rebuild_count") > (
        _counter(before_changed_font, "projection_snapshot_rebuild_count")
    )
