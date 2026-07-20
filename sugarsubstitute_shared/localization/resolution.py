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

"""Resolve manifest languages from platform-independent locale tags."""

from __future__ import annotations

import re
from collections.abc import Sequence

from sugarsubstitute_shared.localization.manifest import load_language_manifest
from sugarsubstitute_shared.localization.models import (
    LanguageDefinition,
    LanguageManifest,
    LanguagePreference,
    ResolvedLocale,
)

_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,8}$")
_SUBTAG_PATTERN = re.compile(r"^[A-Za-z0-9]{1,8}$")


def normalize_locale_tag(raw_tag: str) -> str | None:
    """Canonicalize common BCP-47 and platform locale spellings."""

    candidate = raw_tag.strip()
    if not candidate:
        return None
    candidate = candidate.split("@", maxsplit=1)[0].split(".", maxsplit=1)[0]
    subtags = candidate.replace("_", "-").split("-")
    if not subtags or not _LANGUAGE_PATTERN.fullmatch(subtags[0]):
        return None
    if any(not _SUBTAG_PATTERN.fullmatch(subtag) for subtag in subtags[1:]):
        return None
    normalized = [subtags[0].lower()]
    for subtag in subtags[1:]:
        if len(subtag) == 4 and subtag.isalpha():
            normalized.append(subtag.title())
        elif (len(subtag) == 2 and subtag.isalpha()) or (
            len(subtag) == 3 and subtag.isdigit()
        ):
            normalized.append(subtag.upper())
        else:
            normalized.append(subtag.lower())
    return "-".join(normalized)


def match_language_identifier(
    locale_tag: str,
    *,
    manifest: LanguageManifest | None = None,
) -> str | None:
    """Return the release language matching one locale tag, if supported."""

    registry = manifest or load_language_manifest()
    normalized_tag = normalize_locale_tag(locale_tag)
    if normalized_tag is None:
        return None
    for language in registry.release_languages:
        if any(
            _locale_pattern_matches(normalized_tag, pattern)
            for pattern in language.accepted_system_tags
        ):
            return language.identifier
    return None


def resolve_locale(
    preference: LanguagePreference,
    *,
    ui_languages: Sequence[str],
    process_override: str | None = None,
    manifest: LanguageManifest | None = None,
) -> ResolvedLocale:
    """Resolve one durable request into effective translation and formatting state."""

    registry = manifest or load_language_manifest()
    if process_override is not None:
        language = _required_matched_language(process_override, registry)
        return _resolved_explicit(preference, language)
    if not preference.is_system:
        language = registry.language(preference.language_identifier)
        if not language.release_enabled:
            raise ValueError(
                f"Language is not release-enabled: {preference.language_identifier!r}"
            )
        return _resolved_explicit(preference, language)

    normalized_candidates = tuple(
        normalized
        for raw_tag in ui_languages
        if (normalized := normalize_locale_tag(raw_tag)) is not None
    )
    for normalized_tag in normalized_candidates:
        identifier = match_language_identifier(normalized_tag, manifest=registry)
        if identifier is None:
            continue
        language = registry.language(identifier)
        formatting_locale = _formatting_locale_for_match(language, normalized_tag)
        return ResolvedLocale(
            requested=preference,
            effective_language=language,
            formatting_locale=formatting_locale,
            matched_ui_language=normalized_tag,
        )

    default_language = registry.default_language
    return ResolvedLocale(
        requested=preference,
        effective_language=default_language,
        formatting_locale=_english_fallback_locale(normalized_candidates),
        matched_ui_language=None,
    )


def _required_matched_language(
    locale_tag: str,
    manifest: LanguageManifest,
) -> LanguageDefinition:
    """Return a release language or reject an invalid process handoff."""

    identifier = match_language_identifier(locale_tag, manifest=manifest)
    if identifier is None:
        raise ValueError(f"Unsupported locale override: {locale_tag!r}")
    return manifest.language(identifier)


def _resolved_explicit(
    preference: LanguagePreference,
    language: LanguageDefinition,
) -> ResolvedLocale:
    """Resolve an explicit selection using its manifest formatting default."""

    return ResolvedLocale(
        requested=preference,
        effective_language=language,
        formatting_locale=_default_formatting_locale(language),
        matched_ui_language=None,
    )


def _locale_pattern_matches(locale_tag: str, raw_pattern: str) -> bool:
    """Match exact tags or explicit descendants without broad language leakage."""

    wildcard = raw_pattern.endswith("-*")
    pattern_value = raw_pattern[:-2] if wildcard else raw_pattern
    normalized_pattern = normalize_locale_tag(pattern_value)
    if normalized_pattern is None:
        raise ValueError(f"Invalid accepted_system_tags pattern: {raw_pattern!r}")
    if wildcard:
        return locale_tag.startswith(f"{normalized_pattern}-")
    return locale_tag == normalized_pattern


def _formatting_locale_for_match(
    language: LanguageDefinition,
    matched_locale: str,
) -> str:
    """Preserve a specific supported system locale and expand bare languages."""

    if "-" in matched_locale:
        return matched_locale
    return _default_formatting_locale(language)


def _default_formatting_locale(language: LanguageDefinition) -> str:
    """Return the first valid Qt locale candidate as a canonical BCP-47 tag."""

    for candidate in language.qt_locale_candidates:
        normalized = normalize_locale_tag(candidate)
        if normalized is not None:
            return normalized
    raise ValueError(
        f"Language has no valid Qt locale candidates: {language.identifier!r}"
    )


def _english_fallback_locale(ui_languages: Sequence[str]) -> str:
    """Keep system territory while preventing foreign translated date names."""

    for locale_tag in ui_languages:
        territory = _locale_territory(locale_tag)
        if territory is not None:
            return f"en-{territory}"
    return "en-US"


def _locale_territory(locale_tag: str) -> str | None:
    """Extract one canonical region subtag from an already normalized locale."""

    for subtag in locale_tag.split("-")[1:]:
        if (len(subtag) == 2 and subtag.isalpha()) or (
            len(subtag) == 3 and subtag.isdigit()
        ):
            return subtag.upper()
    return None


__all__ = ["match_language_identifier", "normalize_locale_tag", "resolve_locale"]
