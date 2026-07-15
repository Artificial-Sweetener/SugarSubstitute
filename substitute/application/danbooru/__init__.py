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

"""Expose Danbooru application services without eager feature imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.application.danbooru.content_models import (
        DanbooruContentFreshnessState,
        DanbooruImagePreviewState,
        DanbooruWikiContentLookupResult,
        DanbooruWikiContentPage,
        DanbooruWikiImagePreview,
    )
    from substitute.application.danbooru.dtext_normalization import (
        candidate_titles_for_selection,
        normalize_selection_text,
        prompt_display_text_from_alias,
        prompt_display_text_from_tag,
    )
    from substitute.application.danbooru.image_preview_service import (
        DanbooruImagePreviewService,
    )
    from substitute.application.danbooru.models import (
        DanbooruFailureReason,
        DanbooruImportedPrompt,
        DanbooruPromptImportResult,
        DanbooruUrlClassification,
        DanbooruUrlKind,
        DanbooruWikiLookupResult,
        DanbooruWikiNavigationEntry,
        DanbooruWikiPageView,
    )
    from substitute.application.danbooru.preferences_service import (
        DanbooruPreferenceService,
    )
    from substitute.application.danbooru.recent_posts_service import (
        DanbooruRecentPostsService,
    )
    from substitute.application.danbooru.url_import_service import (
        DanbooruUrlImportService,
    )
    from substitute.application.danbooru.wiki_content_service import (
        DanbooruWikiContentService,
    )
    from substitute.application.danbooru.wiki_inline_resolution_service import (
        DanbooruWikiInlineResolutionService,
    )
    from substitute.application.danbooru.wiki_render_models import (
        DanbooruWikiBlock,
        DanbooruWikiCodeNode,
        DanbooruWikiExternalLinkNode,
        DanbooruWikiImageReference,
        DanbooruWikiImageReferenceBlock,
        DanbooruWikiInlineNode,
        DanbooruWikiLineBreakNode,
        DanbooruWikiListBlock,
        DanbooruWikiListItem,
        DanbooruWikiParagraphBlock,
        DanbooruWikiQuoteBlock,
        DanbooruWikiSearchLinkNode,
        DanbooruWikiSectionContent,
        DanbooruWikiStyledTextNode,
        DanbooruWikiTagChipNode,
        DanbooruWikiTextNode,
        DanbooruWikiWikiLinkNode,
        inline_nodes_contain_tag_chips,
        plain_text_from_inline_nodes,
    )
    from substitute.application.danbooru.wiki_renderer_audit_service import (
        DanbooruWikiRendererAuditFinding,
        DanbooruWikiRendererAuditReport,
        DanbooruWikiRendererAuditService,
    )
    from substitute.application.danbooru.wiki_service import DanbooruWikiService
    from substitute.domain.danbooru import DanbooruImageRatingPolicy

_LAZY_EXPORTS = {
    "candidate_titles_for_selection": (
        "substitute.application.danbooru.dtext_normalization"
    ),
    "DanbooruContentFreshnessState": ("substitute.application.danbooru.content_models"),
    "DanbooruFailureReason": "substitute.application.danbooru.models",
    "DanbooruImagePreviewService": (
        "substitute.application.danbooru.image_preview_service"
    ),
    "DanbooruImageRatingPolicy": "substitute.domain.danbooru",
    "DanbooruImagePreviewState": "substitute.application.danbooru.content_models",
    "DanbooruImportedPrompt": "substitute.application.danbooru.models",
    "DanbooruPreferenceService": (
        "substitute.application.danbooru.preferences_service"
    ),
    "DanbooruRecentPostsService": (
        "substitute.application.danbooru.recent_posts_service"
    ),
    "DanbooruPromptImportResult": "substitute.application.danbooru.models",
    "DanbooruUrlClassification": "substitute.application.danbooru.models",
    "DanbooruUrlImportService": ("substitute.application.danbooru.url_import_service"),
    "DanbooruUrlKind": "substitute.application.danbooru.models",
    "DanbooruWikiContentLookupResult": (
        "substitute.application.danbooru.content_models"
    ),
    "DanbooruWikiContentPage": "substitute.application.danbooru.content_models",
    "DanbooruWikiBlock": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiCodeNode": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiExternalLinkNode": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiContentService": (
        "substitute.application.danbooru.wiki_content_service"
    ),
    "DanbooruWikiImagePreview": "substitute.application.danbooru.content_models",
    "DanbooruWikiImageReference": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiImageReferenceBlock": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiInlineNode": ("substitute.application.danbooru.wiki_render_models"),
    "DanbooruWikiLineBreakNode": ("substitute.application.danbooru.wiki_render_models"),
    "DanbooruWikiListItem": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiInlineResolutionService": (
        "substitute.application.danbooru.wiki_inline_resolution_service"
    ),
    "DanbooruWikiListBlock": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiLookupResult": "substitute.application.danbooru.models",
    "DanbooruWikiNavigationEntry": "substitute.application.danbooru.models",
    "DanbooruWikiPageView": "substitute.application.danbooru.models",
    "DanbooruWikiParagraphBlock": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiQuoteBlock": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiRendererAuditFinding": (
        "substitute.application.danbooru.wiki_renderer_audit_service"
    ),
    "DanbooruWikiRendererAuditReport": (
        "substitute.application.danbooru.wiki_renderer_audit_service"
    ),
    "DanbooruWikiRendererAuditService": (
        "substitute.application.danbooru.wiki_renderer_audit_service"
    ),
    "DanbooruWikiSearchLinkNode": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiSectionContent": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiService": "substitute.application.danbooru.wiki_service",
    "DanbooruWikiStyledTextNode": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "DanbooruWikiTagChipNode": ("substitute.application.danbooru.wiki_render_models"),
    "DanbooruWikiTextNode": "substitute.application.danbooru.wiki_render_models",
    "DanbooruWikiWikiLinkNode": ("substitute.application.danbooru.wiki_render_models"),
    "inline_nodes_contain_tag_chips": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "normalize_selection_text": "substitute.application.danbooru.dtext_normalization",
    "plain_text_from_inline_nodes": (
        "substitute.application.danbooru.wiki_render_models"
    ),
    "prompt_display_text_from_alias": (
        "substitute.application.danbooru.dtext_normalization"
    ),
    "prompt_display_text_from_tag": (
        "substitute.application.danbooru.dtext_normalization"
    ),
}


def __getattr__(name: str) -> object:
    """Load one exported Danbooru application symbol on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "candidate_titles_for_selection",
    "DanbooruContentFreshnessState",
    "DanbooruFailureReason",
    "DanbooruImagePreviewService",
    "DanbooruImageRatingPolicy",
    "DanbooruImagePreviewState",
    "DanbooruImportedPrompt",
    "DanbooruPreferenceService",
    "DanbooruRecentPostsService",
    "DanbooruPromptImportResult",
    "DanbooruUrlClassification",
    "DanbooruUrlImportService",
    "DanbooruUrlKind",
    "DanbooruWikiContentLookupResult",
    "DanbooruWikiContentPage",
    "DanbooruWikiBlock",
    "DanbooruWikiCodeNode",
    "DanbooruWikiExternalLinkNode",
    "DanbooruWikiContentService",
    "DanbooruWikiImagePreview",
    "DanbooruWikiImageReference",
    "DanbooruWikiImageReferenceBlock",
    "DanbooruWikiInlineNode",
    "DanbooruWikiLineBreakNode",
    "DanbooruWikiListItem",
    "DanbooruWikiInlineResolutionService",
    "DanbooruWikiListBlock",
    "DanbooruWikiLookupResult",
    "DanbooruWikiNavigationEntry",
    "DanbooruWikiPageView",
    "DanbooruWikiParagraphBlock",
    "DanbooruWikiQuoteBlock",
    "DanbooruWikiRendererAuditFinding",
    "DanbooruWikiRendererAuditReport",
    "DanbooruWikiRendererAuditService",
    "DanbooruWikiSearchLinkNode",
    "DanbooruWikiSectionContent",
    "DanbooruWikiStyledTextNode",
    "DanbooruWikiService",
    "DanbooruWikiTagChipNode",
    "DanbooruWikiTextNode",
    "DanbooruWikiWikiLinkNode",
    "inline_nodes_contain_tag_chips",
    "normalize_selection_text",
    "plain_text_from_inline_nodes",
    "prompt_display_text_from_alias",
    "prompt_display_text_from_tag",
]
