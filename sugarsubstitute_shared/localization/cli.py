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

"""Validate and format locale values passed between executable processes."""

from __future__ import annotations

from sugarsubstitute_shared.localization.manifest import load_language_manifest
from sugarsubstitute_shared.localization.models import LanguageManifest
from sugarsubstitute_shared.localization.resolution import match_language_identifier


def parse_locale_override(
    raw_value: str,
    *,
    manifest: LanguageManifest | None = None,
) -> str:
    """Convert one locale-like argument to a supported effective language ID."""

    registry = manifest or load_language_manifest()
    identifier = match_language_identifier(raw_value, manifest=registry)
    if identifier is None:
        raise ValueError(f"Unsupported locale override: {raw_value!r}")
    return identifier


def format_locale_argument(
    language_identifier: str,
    *,
    manifest: LanguageManifest | None = None,
) -> str:
    """Format a validated effective language for crash-safe process handoff."""

    registry = manifest or load_language_manifest()
    language = registry.language(language_identifier)
    if not language.release_enabled:
        raise ValueError(f"Language is not release-enabled: {language_identifier!r}")
    return f"--locale={language.identifier}"


__all__ = ["format_locale_argument", "parse_locale_override"]
