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

"""Unit tests for Danbooru wiki inline chip eligibility."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru import (
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiInlineResolutionService,
    DanbooruWikiParagraphBlock,
    DanbooruWikiSearchLinkNode,
    DanbooruWikiSectionContent,
    DanbooruWikiTagChipNode,
    DanbooruWikiWikiLinkNode,
)
from substitute.domain.danbooru import (
    DanbooruCachedTag,
    DanbooruLookupStatus,
    DanbooruTagRecord,
)
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


def test_inline_resolution_service_chipifies_ordinary_wiki_titles_without_lookup(
    tmp_path: Path,
) -> None:
    """Ordinary wiki titles should become chips without extra confirmation work."""

    service = DanbooruWikiInlineResolutionService(
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="Definition",
                blocks=(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=(
                            DanbooruWikiWikiLinkNode(
                                target_title="short_hair",
                                display_label="short hair",
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [paragraph] = section.blocks
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert paragraph.inline_nodes == (
        DanbooruWikiTagChipNode(
            tag_name="short_hair",
            display_label="short hair",
            category_name=None,
        ),
    )


def test_inline_resolution_service_keeps_known_non_tag_namespaces_as_links(
    tmp_path: Path,
) -> None:
    """Documented Danbooru wiki namespaces should remain normal wiki links."""

    service = DanbooruWikiInlineResolutionService(
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="See also",
                blocks=(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=(
                            DanbooruWikiWikiLinkNode(
                                target_title="Tag Group: Hair Styles",
                                display_label="Tag Group: Hair Styles",
                            ),
                            DanbooruWikiWikiLinkNode(
                                target_title="pool_group:style",
                                display_label="pool_group:style",
                            ),
                            DanbooruWikiWikiLinkNode(
                                target_title="help:users",
                                display_label="help:users",
                            ),
                            DanbooruWikiWikiLinkNode(
                                target_title="howto:flag",
                                display_label="howto:flag",
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [paragraph] = section.blocks
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert paragraph.inline_nodes == (
        DanbooruWikiWikiLinkNode(
            target_title="Tag Group: Hair Styles",
            display_label="Tag Group: Hair Styles",
        ),
        DanbooruWikiWikiLinkNode(
            target_title="pool_group:style",
            display_label="pool_group:style",
        ),
        DanbooruWikiWikiLinkNode(
            target_title="help:users",
            display_label="help:users",
        ),
        DanbooruWikiWikiLinkNode(
            target_title="howto:flag",
            display_label="howto:flag",
        ),
    )


def test_inline_resolution_service_handles_mixed_case_and_spaced_namespace_forms(
    tmp_path: Path,
) -> None:
    """Namespace detection should normalize case and underscore/space variants."""

    service = DanbooruWikiInlineResolutionService(
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="See also",
                blocks=(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=(
                            DanbooruWikiWikiLinkNode(
                                target_title="Howto:Flag",
                                display_label="Howto:Flag",
                            ),
                            DanbooruWikiWikiLinkNode(
                                target_title="Pool Group:Expression",
                                display_label="Pool Group:Expression",
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [paragraph] = section.blocks
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert paragraph.inline_nodes == (
        DanbooruWikiWikiLinkNode(
            target_title="Howto:Flag",
            display_label="Howto:Flag",
        ),
        DanbooruWikiWikiLinkNode(
            target_title="Pool Group:Expression",
            display_label="Pool Group:Expression",
        ),
    )


def test_inline_resolution_service_uses_cached_tag_metadata_only_for_category_enrichment(
    tmp_path: Path,
) -> None:
    """Cached tag metadata should tint chips without requiring network confirmation."""

    cache_repository = SqliteDanbooruCacheStore(tmp_path)
    cache_repository.save_cached_tag(
        DanbooruCachedTag(
            name="saber_(fate)",
            lookup_status=DanbooruLookupStatus.FOUND,
            tag=_tag_record(name="saber_(fate)", category=4),
            fetched_at="2026-05-14T10:00:00+00:00",
            expires_at="2026-05-21T10:00:00+00:00",
        )
    )
    service = DanbooruWikiInlineResolutionService(
        cache_repository=cache_repository,
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="Definition",
                blocks=(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=(
                            DanbooruWikiWikiLinkNode(
                                target_title="saber_(fate)",
                                display_label="Saber",
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [paragraph] = section.blocks
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert paragraph.inline_nodes == (
        DanbooruWikiTagChipNode(
            tag_name="saber_(fate)",
            display_label="Saber",
            category_name="character",
        ),
    )


def test_inline_resolution_service_leaves_search_links_non_chip(
    tmp_path: Path,
) -> None:
    """Danbooru search-expression links should never become chips."""

    service = DanbooruWikiInlineResolutionService(
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="Definition",
                blocks=(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=(
                            DanbooruWikiSearchLinkNode(
                                query_text="mpixels:<=0.25",
                                href="https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25",
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [paragraph] = section.blocks
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert isinstance(paragraph.inline_nodes[0], DanbooruWikiSearchLinkNode)


def test_inline_resolution_service_promotes_ordinary_caption_links_to_chips(
    tmp_path: Path,
) -> None:
    """Image captions should chipify ordinary wiki links through the same rule."""

    service = DanbooruWikiInlineResolutionService(
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
    )

    [section] = service.resolve_sections(
        (
            DanbooruWikiSectionContent(
                heading="Examples",
                blocks=(
                    DanbooruWikiImageReferenceBlock(
                        items=(
                            DanbooruWikiImageReference(
                                source_kind="post",
                                source_id=12345,
                                caption_text="arched bangs",
                                caption_nodes=(
                                    DanbooruWikiWikiLinkNode(
                                        target_title="arched_bangs",
                                        display_label="arched bangs",
                                    ),
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    )

    [image_block] = section.blocks
    assert isinstance(image_block, DanbooruWikiImageReferenceBlock)
    [item] = image_block.items
    assert item.caption_nodes == (
        DanbooruWikiTagChipNode(
            tag_name="arched_bangs",
            display_label="arched bangs",
            category_name=None,
        ),
    )


def _tag_record(*, name: str, category: int) -> DanbooruTagRecord:
    """Return one representative Danbooru tag record for resolution tests."""

    return DanbooruTagRecord(
        tag_id=11,
        created_at="2013-02-28T00:04:36.440-05:00",
        updated_at="2019-08-26T20:40:54.525-04:00",
        name=name,
        category=category,
        post_count=124500,
        is_deprecated=False,
    )
