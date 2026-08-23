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

"""Verify prompt reorder preview-projection observability."""

from __future__ import annotations

import logging

import pytest


from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.theme import (
    semantic_palette_from_theme,
)

from .support import (
    _LOGGER_NAME,
    _service,
    _context,
    _build_reorder_preview_state,
)


def test_reorder_projection_service_cache_logging_context_is_prompt_safe(
    app: QApplication,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cache diagnostics should log hashes and counts without prompt content."""

    _ = app
    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)
    prompt_text = "secret phrase alpha, beta, gamma"
    service = _service()
    preview_state = _build_reorder_preview_state(
        prompt_text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    service.set_preview_state(
        preview_state,
        context=_context(active_drop_target_identity=("line", 0, 1)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "secret phrase" not in messages
    assert "source_text" not in messages
    assert "projection_cache_snapshot_hash" in messages
