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

"""Project prompt source text into application-facing prompt document views."""

from __future__ import annotations

import time

from substitute.domain.prompt import PromptDocument
from substitute.shared.logging.logger import get_logger, log_timing

from .prompt_document_cache import (
    cached_prompt_document,
    cached_prompt_document_view,
    prewarm_prompt_document_views as prewarm_cached_prompt_document_views,
    store_prompt_document_view,
)
from .prompt_document_view_mapper import prompt_document_view_from_domain
from .prompt_document_views import PromptDocumentView

_LOGGER = get_logger("application.prompt_editor.prompt_document_projector")


class PromptDocumentProjector:
    """Own prompt parsing, projection, and projection-cache orchestration."""

    def parse_document(self, text: str) -> PromptDocument:
        """Parse plain prompt text into the canonical domain document."""

        return cached_prompt_document(text)

    def build_document_view(self, text: str) -> PromptDocumentView:
        """Build one application-safe prompt snapshot from plain text."""

        started_at = time.perf_counter()
        cached = cached_prompt_document_view(text)
        if cached is not None:
            log_timing(
                _LOGGER,
                "Prompt document view projection reused cached view",
                started_at=started_at,
                level="debug",
                operation="build_document_view",
                cache_name="document_view",
                cache_hit=True,
                text_length=len(text),
            )
            return cached

        document_view = self.build_document_view_from_document(
            self.parse_document(text)
        )
        store_prompt_document_view(text, document_view)
        log_timing(
            _LOGGER,
            "Prompt document view projection built view",
            started_at=started_at,
            level="debug",
            operation="build_document_view",
            cache_name="document_view",
            cache_hit=False,
            text_length=len(text),
            segment_count=len(document_view.segments),
        )
        return document_view

    def prewarm_document_views(self, texts: tuple[str, ...]) -> int:
        """Populate process-wide prompt document caches for restored prompt texts."""

        started_at = time.perf_counter()
        warmed_count = prewarm_cached_prompt_document_views(
            texts,
            self.build_document_view,
        )
        log_timing(
            _LOGGER,
            "Prompt document views prewarmed",
            started_at=started_at,
            level="debug",
            operation="prewarm_document_views",
            text_count=len(texts),
            warmed_count=warmed_count,
        )
        return warmed_count

    def build_document_view_from_document(
        self,
        document: PromptDocument,
    ) -> PromptDocumentView:
        """Project one domain prompt document into the application snapshot."""

        started_at = time.perf_counter()
        document_view = prompt_document_view_from_domain(document)
        log_timing(
            _LOGGER,
            "Prompt domain document projected",
            started_at=started_at,
            level="debug",
            operation="build_document_view_from_document",
            text_length=len(document.source_text),
            segment_count=len(document_view.segments),
        )
        return document_view


__all__ = ["PromptDocumentProjector"]
