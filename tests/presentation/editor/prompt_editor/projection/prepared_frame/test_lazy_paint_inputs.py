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

"""Verify prepared paint inputs resolve only visible projection content."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionInlineObjectFragment,
)
from substitute.presentation.editor.prompt_editor.projection.content_inline_bindings import (
    prepare_base_inline_bindings,
)
from substitute.presentation.editor.prompt_editor.projection.content_text_styles import (
    prepare_base_text_styles,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer import (
    PromptRichInlineObjectRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer_registry import (
    PromptProjectionInlineObjectRendererRegistry,
)


class _CountingProjectionDocument:
    """Return one run and token while counting semantic lookups."""

    def __init__(self) -> None:
        """Initialize deterministic projection values and counters."""

        self.run = PromptProjectionRun(
            run_id="run",
            kind=PromptProjectionRunKind.INLINE_OBJECT,
            source_start=0,
            source_end=4,
            display_text="tag",
            source_positions=range(0, 5),
            projection_start=0,
            projection_end=1,
            token_id="token",
            renderer_key="renderer",
        )
        self.token = PromptProjectionToken(
            token_id="token",
            kind=PromptProjectionTokenKind.WILDCARD,
            source_start=0,
            source_end=4,
            display_text="tag",
        )
        self.run_lookups = 0
        self.token_lookups = 0

    def run_by_id(self, run_id: str | None) -> PromptProjectionRun | None:
        """Return the configured run and count the lookup."""

        self.run_lookups += 1
        return self.run if run_id == self.run.run_id else None

    def token_by_id(self, token_id: str | None) -> PromptProjectionToken | None:
        """Return the configured token and count the lookup."""

        self.token_lookups += 1
        return self.token if token_id == self.token.token_id else None


def test_base_text_styles_defer_run_lookup_until_visible_use() -> None:
    """Preparing a frame must not style every run in a long document."""

    document = _CountingProjectionDocument()
    styles = prepare_base_text_styles(
        cast(PromptProjectionDocument, document),
        base_font=QFont(),
        palette=QPalette(),
        semantic_palette=None,
    )

    assert document.run_lookups == 0

    style = styles.style_for_run("run")

    assert style is not None
    assert styles.style_for_run("run") is style
    assert document.run_lookups == 1


def test_base_inline_bindings_defer_semantic_lookup_until_visible_use() -> None:
    """Preparing a frame must not bind every off-screen inline fragment."""

    document = _CountingProjectionDocument()
    renderer = cast(
        PromptRichInlineObjectRenderer,
        SimpleNamespace(renderer_key="renderer"),
    )
    bindings = prepare_base_inline_bindings(
        cast(PromptProjectionDocument, document),
        renderers=PromptProjectionInlineObjectRendererRegistry((renderer,)),
    )
    fragment = PromptProjectionInlineObjectFragment(
        run_id="run",
        token_id="token",
        renderer_key="renderer",
        projection_start=0,
        projection_end=1,
        source_positions=range(0, 5),
        rect=QRectF(0.0, 0.0, 10.0, 10.0),
    )

    assert document.run_lookups == 0
    assert document.token_lookups == 0

    binding = bindings.binding(fragment)

    assert binding is not None
    assert binding.run is document.run
    assert binding.token is document.token
    assert bindings.binding(fragment) is binding
    assert document.run_lookups == 1
    assert document.token_lookups == 1
