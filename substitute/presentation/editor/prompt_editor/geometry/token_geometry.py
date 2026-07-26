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

"""Resolve token rectangles and renderer-defined anchor geometry."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRunKind,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from ..projection.tokens import (
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)
from ..layout.models import (
    PromptProjectionInlineObjectFragment,
    PromptProjectionLayoutSnapshot,
    PromptProjectionTextFragment,
)
from .state import PromptProjectionGeometryInput


@dataclass(frozen=True, slots=True)
class PromptTokenGeometry:
    """Resolve token geometry from one immutable layout input."""

    input: PromptProjectionGeometryInput

    @property
    def _projection_document(self) -> PromptProjectionDocument:
        """Return the immutable projected document."""

        return self.input.projection_document

    @property
    def _snapshot(self) -> PromptProjectionLayoutSnapshot:
        """Return the immutable layout snapshot."""

        return self.input.layout_snapshot

    @property
    def _base_font(self) -> QFont:
        """Return the font captured with this layout."""

        return self.input.base_font

    @property
    def inline_object_renderers(self) -> PromptProjectionInlineObjectRendererRegistry:
        """Return the stable inline renderer registry."""

        return self.input.inline_object_renderers

    def token_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the viewport-local union rect occupied by one semantic token."""

        token_fragments = self.fragments_for_token(token)
        if not token_fragments:
            return None
        token_rect = QRectF(token_fragments[0].rect)
        for fragment in token_fragments[1:]:
            token_rect = token_rect.united(fragment.rect)
        return token_rect.translated(0.0, -scroll_offset)

    def token_anchor_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the renderer-defined anchor rect for one projected token."""

        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is not PromptProjectionRunKind.INLINE_OBJECT:
                continue
            renderer = self.inline_object_renderers.renderer_for(run.renderer_key)
            if renderer is None:
                continue
            object_fragments = self._snapshot.inline_object_fragments_for_run(
                run.run_id
            )
            if not object_fragments:
                continue
            anchor_rect = renderer.anchor_rect(
                run,
                token,
                object_fragments[-1].rect.translated(0.0, -scroll_offset),
                base_font=self._base_font,
            )
            if anchor_rect is not None:
                return anchor_rect
        return None

    def token_weight_text_rect(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> QRectF | None:
        """Return the viewport-local slot rect of one emphasis token weight label."""

        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is not PromptProjectionRunKind.INLINE_OBJECT:
                continue
            renderer = self.inline_object_renderers.renderer_for(run.renderer_key)
            if not isinstance(
                renderer,
                PromptEmphasisSuffixRenderer
                | PromptLoraInlineObjectRenderer
                | PromptWildcardInlineObjectRenderer,
            ):
                continue
            object_fragments = self._snapshot.inline_object_fragments_for_run(
                run.run_id
            )
            if not object_fragments:
                continue
            weight_rect = renderer.weight_text_rect(
                run,
                token,
                object_fragments[-1].rect.translated(0.0, -scroll_offset),
                base_font=self._base_font,
            )
            if weight_rect is not None:
                return weight_rect
        return None

    def token_fragments(
        self,
        token: PromptProjectionToken,
        *,
        scroll_offset: float = 0.0,
    ) -> tuple[QRectF, ...]:
        """Return the viewport-local visible fragments owned by one token."""

        return tuple(
            fragment.rect.translated(0.0, -scroll_offset)
            for fragment in self.fragments_for_token(token)
        )

    def token_at_viewport_position(
        self,
        position: QPointF,
        *,
        scroll_offset: float,
    ) -> PromptProjectionToken | None:
        """Return the topmost projected token painted beneath one viewport point."""

        for token in reversed(self._projection_document.tokens):
            if any(
                fragment.contains(position)
                for fragment in self.token_fragments(
                    token,
                    scroll_offset=scroll_offset,
                )
            ):
                return token
        return None

    def fragments_for_token(
        self,
        token: PromptProjectionToken,
    ) -> tuple[
        PromptProjectionTextFragment | PromptProjectionInlineObjectFragment,
        ...,
    ]:
        """Return every visible fragment owned by one semantic token."""

        fragments: list[
            PromptProjectionTextFragment | PromptProjectionInlineObjectFragment
        ] = []
        for run in self._projection_document.runs_for_token(token.token_id):
            if run.kind is PromptProjectionRunKind.TEXT:
                fragments.extend(self._snapshot.text_fragments_for_run(run.run_id))
                continue
            fragments.extend(self._snapshot.inline_object_fragments_for_run(run.run_id))
        return tuple(fragments)


__all__ = ["PromptTokenGeometry"]
