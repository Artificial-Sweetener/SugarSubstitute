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

"""Classify Danbooru URLs and convert resolved posts into prompt text."""

from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import urlparse

from substitute.application.danbooru.models import (
    DanbooruFailureReason,
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlKind,
)
from substitute.application.prompt_editor import autocomplete_replacement_text
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info

_LOGGER = get_logger("application.danbooru.url_import_service")
_POST_PATH_PATTERN = re.compile(r"^/posts/(?P<post_id>\d+)$")
_CDN_MD5_PATTERN = re.compile(r"(?P<md5>[0-9a-fA-F]{32})(?:\.[A-Za-z0-9]+)$")
_SUPPORTED_POST_HOSTS = frozenset({"danbooru.donmai.us", "www.danbooru.donmai.us"})
_SUPPORTED_CDN_HOSTS = frozenset({"cdn.donmai.us"})


class DanbooruUrlImportService:
    """Resolve supported Danbooru URLs into prompt-safe imported tag text."""

    def __init__(self, *, client: "DanbooruPostLookupClient") -> None:
        """Store the Danbooru client used for post lookups."""

        self._client = client

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Return a supported Danbooru URL classification when possible."""

        stripped = text.strip()
        if not stripped:
            return None
        parsed = urlparse(stripped)
        host = parsed.netloc.casefold()
        if host in _SUPPORTED_POST_HOSTS:
            path_match = _POST_PATH_PATTERN.fullmatch(parsed.path)
            if path_match is None:
                return None
            return DanbooruUrlClassification(
                url=stripped,
                kind=DanbooruUrlKind.POST,
                lookup_value=path_match.group("post_id"),
            )
        if host in _SUPPORTED_CDN_HOSTS:
            filename = parsed.path.rsplit("/", 1)[-1]
            md5_match = _CDN_MD5_PATTERN.search(filename)
            if md5_match is None:
                return None
            return DanbooruUrlClassification(
                url=stripped,
                kind=DanbooruUrlKind.CDN,
                lookup_value=md5_match.group("md5").lower(),
            )
        return None

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Return prompt text imported from one supported Danbooru URL."""

        classification = self.classify_url(text)
        if classification is None:
            log_debug(_LOGGER, "Danbooru URL import rejected unsupported text.")
            return DanbooruPromptImportResult(
                imported_prompt=None,
                failure_reason=DanbooruFailureReason.UNSUPPORTED_URL,
            )
        log_debug(
            _LOGGER,
            "Danbooru URL classified for prompt import.",
            url_kind=classification.kind.value,
            lookup_value=classification.lookup_value,
        )
        post_result = (
            self._client.get_post_by_id(int(classification.lookup_value))
            if classification.kind is DanbooruUrlKind.POST
            else self._client.get_post_by_md5(classification.lookup_value)
        )
        if (
            post_result.status is not DanbooruLookupStatus.FOUND
            or post_result.post is None
        ):
            return DanbooruPromptImportResult(
                imported_prompt=None,
                failure_reason=_failure_reason_from_lookup_status(post_result.status),
                error=post_result.error,
                classification=classification,
            )

        imported_prompt = _imported_prompt_from_post(post_result.post)
        log_info(
            _LOGGER,
            "Danbooru URL import resolved prompt tags.",
            url_kind=classification.kind.value,
            post_id=imported_prompt.source_post_id,
            included_tag_count=len(imported_prompt.included_tags),
            excluded_tag_count=len(imported_prompt.excluded_tags),
        )
        return DanbooruPromptImportResult(
            imported_prompt=imported_prompt,
            classification=classification,
        )


def _imported_prompt_from_post(post: DanbooruPostRecord) -> DanbooruImportedPrompt:
    """Convert one Danbooru post into prompt insertion text and tag group details."""

    included_tags = _deduplicated_tags(
        post.tag_string_general,
        post.tag_string_artist,
        post.tag_string_copyright,
        post.tag_string_character,
    )
    excluded_tags = _deduplicated_tags(post.tag_string_meta)
    display_text = ", ".join(
        autocomplete_replacement_text(tag) for tag in included_tags
    )
    return DanbooruImportedPrompt(
        display_text=display_text,
        source_post_id=post.post_id,
        included_tags=included_tags,
        excluded_tags=excluded_tags,
    )


def _deduplicated_tags(*tag_groups: str) -> tuple[str, ...]:
    """Return tag tokens in stable order with duplicates removed."""

    tags: list[str] = []
    seen: set[str] = set()
    for tag_group in tag_groups:
        for raw_tag in tag_group.split():
            normalized = raw_tag.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tags.append(normalized)
    return tuple(tags)


def _failure_reason_from_lookup_status(
    status: DanbooruLookupStatus,
) -> DanbooruFailureReason:
    """Map one provider-layer lookup status to the application failure reason."""

    if status is DanbooruLookupStatus.NOT_FOUND:
        return DanbooruFailureReason.NOT_FOUND
    if status is DanbooruLookupStatus.UNAVAILABLE:
        return DanbooruFailureReason.UNAVAILABLE
    return DanbooruFailureReason.INVALID_RESPONSE


class DanbooruPostLookupClient(Protocol):
    """Describe the client surface needed for Danbooru post imports."""

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return one post lookup result by Danbooru numeric post id."""

    def get_post_by_md5(self, md5: str) -> DanbooruPostLookupResult:
        """Return one post lookup result by exact Danbooru media MD5."""


__all__ = ["DanbooruUrlImportService"]
