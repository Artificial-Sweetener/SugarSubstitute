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

"""Audit cached Danbooru wiki bodies for notable DText constructs."""

from __future__ import annotations

from dataclasses import dataclass
import re

from substitute.application.ports import DanbooruCacheRepository
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.danbooru.wiki_renderer_audit_service")
_EXCERPT_RADIUS = 48
_AUDIT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "quoted_relative_danbooru_link",
        re.compile(r'"[^"\n]+":/[^\s<]+'),
    ),
    (
        "quoted_external_link",
        re.compile(r'"[^"\n]+":https?://[^\s<]+'),
    ),
)


@dataclass(frozen=True, slots=True)
class DanbooruWikiRendererAuditFinding:
    """Describe one cached markup occurrence worth renderer-aware review."""

    pattern_name: str
    page_title: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiRendererAuditReport:
    """Describe the findings produced from one cached wiki audit pass."""

    cached_page_count: int
    findings: tuple[DanbooruWikiRendererAuditFinding, ...]


class DanbooruWikiRendererAuditService:
    """Scan cached Danbooru wiki bodies for notable renderer syntax patterns."""

    def __init__(self, cache_repository: DanbooruCacheRepository) -> None:
        """Store the repository used to inspect cached wiki bodies."""

        self._cache_repository = cache_repository

    def audit_cached_pages(self) -> DanbooruWikiRendererAuditReport:
        """Return one deterministic report over the currently cached wiki pages."""

        cached_pages = self._cache_repository.list_cached_wiki_pages()
        findings: list[DanbooruWikiRendererAuditFinding] = []
        for entry in cached_pages:
            if entry.wiki_page is None:
                continue
            body = entry.wiki_page.body
            for pattern_name, pattern in _AUDIT_PATTERNS:
                for match in pattern.finditer(body):
                    findings.append(
                        DanbooruWikiRendererAuditFinding(
                            pattern_name=pattern_name,
                            page_title=entry.title,
                            excerpt=_excerpt_around_match(
                                body,
                                start=match.start(),
                                end=match.end(),
                            ),
                        )
                    )
        report = DanbooruWikiRendererAuditReport(
            cached_page_count=len(cached_pages),
            findings=tuple(findings),
        )
        if report.findings:
            log_warning(
                _LOGGER,
                "Danbooru wiki renderer audit found notable cached syntax.",
                cached_page_count=report.cached_page_count,
                finding_count=len(report.findings),
                pattern_names=",".join(
                    sorted({finding.pattern_name for finding in report.findings})
                ),
            )
        else:
            log_info(
                _LOGGER,
                "Danbooru wiki renderer audit found no notable cached syntax.",
                cached_page_count=report.cached_page_count,
            )
        return report


def _excerpt_around_match(body: str, *, start: int, end: int) -> str:
    """Return one compact single-line excerpt around a matched syntax fragment."""

    excerpt_start = max(0, start - _EXCERPT_RADIUS)
    excerpt_end = min(len(body), end + _EXCERPT_RADIUS)
    excerpt = body[excerpt_start:excerpt_end].replace("\r", " ").replace("\n", " ")
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if excerpt_start > 0:
        excerpt = f"...{excerpt}"
    if excerpt_end < len(body):
        excerpt = f"{excerpt}..."
    return excerpt


__all__ = [
    "DanbooruWikiRendererAuditFinding",
    "DanbooruWikiRendererAuditReport",
    "DanbooruWikiRendererAuditService",
]
