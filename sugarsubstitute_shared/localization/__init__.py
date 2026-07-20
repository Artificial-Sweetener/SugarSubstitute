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

"""Expose the Qt-free localization API shared by every executable."""

from sugarsubstitute_shared.localization.cli import (
    format_locale_argument,
    parse_locale_override,
)
from sugarsubstitute_shared.localization.application_message import (
    ApplicationMessage,
    ApplicationText,
    app_text,
    opaque_text,
    render_source_application_text,
)
from sugarsubstitute_shared.localization.file_store import (
    LOCALIZATION_PREFERENCE_SCHEMA_VERSION,
    LocalizationPreferenceStore,
)
from sugarsubstitute_shared.localization.early_startup import (
    resolve_early_startup_locale,
)
from sugarsubstitute_shared.localization.manifest import load_language_manifest
from sugarsubstitute_shared.localization.models import (
    FluentCatalogSource,
    LanguageDefinition,
    LanguageManifest,
    LanguagePreference,
    ResolvedLocale,
    TextDirection,
)
from sugarsubstitute_shared.localization.resolution import (
    match_language_identifier,
    normalize_locale_tag,
    resolve_locale,
)

__all__ = [
    "ApplicationMessage",
    "ApplicationText",
    "LOCALIZATION_PREFERENCE_SCHEMA_VERSION",
    "FluentCatalogSource",
    "LanguageDefinition",
    "LanguageManifest",
    "LanguagePreference",
    "LocalizationPreferenceStore",
    "ResolvedLocale",
    "TextDirection",
    "app_text",
    "opaque_text",
    "format_locale_argument",
    "load_language_manifest",
    "match_language_identifier",
    "normalize_locale_tag",
    "parse_locale_override",
    "resolve_locale",
    "resolve_early_startup_locale",
    "render_source_application_text",
]
