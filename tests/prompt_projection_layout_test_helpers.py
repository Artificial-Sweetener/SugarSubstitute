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

"""Build deterministic projection layouts for focused owner tests."""

from __future__ import annotations

from PySide6.QtGui import QFont, QPalette

from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfileService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.domain.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)


def projection_layout_for(
    text: str,
    *,
    active_span_range: tuple[int, int] | None = None,
    decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    scene_error_keys: frozenset[str] = frozenset(),
    semantic_palette: SemanticPalette | None = None,
    text_width: float = 220.0,
) -> tuple[PromptLayoutEditToFrameCoordinator, PromptProjectionDocument]:
    """Build one projection layout for the supplied prompt text."""

    ensure_qapp()
    document_view, projection = projection_document_for(
        text,
        active_span_range=active_span_range,
        decoration_accent_ranges=decoration_accent_ranges,
        display_mode=display_mode,
        scene_error_keys=scene_error_keys,
    )
    layout = PromptLayoutEditToFrameCoordinator(
        PromptProjectionInlineObjectRendererRegistry(
            (
                PromptEmphasisPrefixRenderer(),
                PromptEmphasisSuffixRenderer(),
                PromptWildcardInlineObjectRenderer(),
            )
        )
    )
    layout.set_base_font(QFont())
    layout.frame.set_palette(QPalette())
    layout.frame.set_semantic_palette(semantic_palette)
    layout.set_projection(projection, prompt_document_view=document_view)
    layout.set_text_width(text_width)
    return layout, projection


def projection_document_for(
    text: str,
    *,
    active_span_range: tuple[int, int] | None = None,
    decoration_accent_ranges: tuple[tuple[int, int], ...] = (),
    display_mode: PromptProjectionDisplayMode = PromptProjectionDisplayMode.PROJECTED,
    scene_error_keys: frozenset[str] = frozenset(),
) -> tuple[PromptDocumentView, PromptProjectionDocument]:
    """Build one document view and matching prompt projection."""

    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(StaticPromptWildcardCatalogGateway({}))
    document_view = document_service.build_document_view(text)
    render_plan = syntax_service.build_render_plan(
        document_view,
        PromptSyntaxProfileService().default_profile(),
    )
    projection = PromptProjectionBuilder().build_projection(
        document_view,
        render_plan,
        display_mode=display_mode,
        session=PromptProjectionSession(),
        active_span_range=active_span_range,
        decoration_accent_ranges=decoration_accent_ranges,
        scene_error_keys=scene_error_keys,
    )
    return document_view, projection


__all__ = ["projection_document_for", "projection_layout_for"]
