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

"""Search ordered Settings catalog metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass

from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
    SettingsSectionEntry,
    ordered_settings_pages,
)
from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    ApplicationText,
    render_application_text,
)

_TOKEN_SEPARATOR_PATTERN = re.compile(r"[^\w{}#]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SettingsSearchResult:
    """Describe one ordered Settings search match."""

    page: SettingsPageEntry
    section: SettingsSectionEntry
    control: SettingsControlEntry

    @property
    def breadcrumb(self) -> str:
        """Return compact page and section context for the result."""

        return f"{_render(self.page.title)} > {_render(self.section.title)}"

    @property
    def page_id(self) -> str:
        """Return the Settings page id that owns this result."""

        return self.page.page_id

    @property
    def setting_id(self) -> str:
        """Return the concrete catalog setting id for this result."""

        return self.control.setting_id

    @property
    def section_id(self) -> str:
        """Return the Settings section id that contains this result."""

        return self.section.section_id


def search_settings_catalog(
    pages: tuple[SettingsPageEntry, ...],
    query: str,
) -> tuple[SettingsSearchResult, ...]:
    """Return catalog controls matching all query tokens in display order."""

    tokens = _query_tokens(query)
    if not tokens:
        return ()
    results: list[SettingsSearchResult] = []
    for page in ordered_settings_pages(pages):
        for section in page.visible_sections():
            for control in section.visible_controls():
                haystack = _searchable_tokens(page, section, control)
                if all(token in haystack for token in tokens):
                    results.append(
                        SettingsSearchResult(
                            page=page,
                            section=section,
                            control=control,
                        )
                    )
    return tuple(results)


def _query_tokens(query: str) -> tuple[str, ...]:
    """Normalize one user query into deterministic match tokens."""

    normalized = _TOKEN_SEPARATOR_PATTERN.sub(" ", query.casefold())
    return tuple(token for token in normalized.split() if token)


def _searchable_tokens(
    page: SettingsPageEntry,
    section: SettingsSectionEntry,
    control: SettingsControlEntry,
) -> frozenset[str]:
    """Return indexed tokens for one catalog control."""

    text = " ".join(
        (
            _render(page.title),
            _render(page.subtitle),
            _render(section.title),
            _render(section.subtitle),
            _render(control.title),
            _render(control.description),
            " ".join(control.keywords),
        )
    )
    return frozenset(_query_tokens(text))


def _render(text: ApplicationText) -> str:
    """Resolve marked catalog copy for the active search language."""

    if isinstance(text, ApplicationMessage):
        return render_application_text(text)
    return text


__all__ = ["SettingsSearchResult", "search_settings_catalog"]
