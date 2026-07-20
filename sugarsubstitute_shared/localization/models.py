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

"""Define immutable locale values shared without importing Qt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

TextDirection: TypeAlias = Literal["left-to-right", "right-to-left"]
FluentCatalogSource: TypeAlias = Literal["none", "shared", "upstream"]


@dataclass(frozen=True, slots=True)
class LanguagePreference:
    """Represent automatic selection or one explicit manifest language."""

    _language_identifier: str | None

    def __post_init__(self) -> None:
        """Reject malformed values before they reach persistence or resolution."""

        if self._language_identifier is not None and (
            not self._language_identifier or self._language_identifier == "system"
        ):
            raise ValueError(
                "An explicit language identifier must not be empty or system."
            )

    @classmethod
    def system(cls) -> LanguagePreference:
        """Create the durable automatic-selection preference."""

        return cls(None)

    @classmethod
    def explicit(cls, language_identifier: str) -> LanguagePreference:
        """Create an explicit preference whose support is manifest-validated later."""

        return cls(language_identifier)

    @property
    def is_system(self) -> bool:
        """Return whether machine UI languages determine the effective language."""

        return self._language_identifier is None

    @property
    def language_identifier(self) -> str:
        """Return the explicit language identifier or reject automatic selection."""

        if self._language_identifier is None:
            raise ValueError(
                "The system language preference has no language identifier."
            )
        return self._language_identifier

    @property
    def storage_value(self) -> str:
        """Return the stable value persisted across machine-language changes."""

        return self._language_identifier or "system"


@dataclass(frozen=True, slots=True)
class LanguageDefinition:
    """Describe one language entirely through validated runtime manifest data."""

    identifier: str
    native_display_name: str
    qt_locale_candidates: tuple[str, ...]
    accepted_system_tags: tuple[str, ...]
    comfy_catalog_aliases: tuple[str, ...]
    app_qm: str | None
    launcher_qm: str | None
    qtbase_qm: str | None
    fluent_qm: str | None
    fluent_catalog_source: FluentCatalogSource
    text_direction: TextDirection
    font_profile: str
    release_enabled: bool


class LanguageManifest:
    """Own the validated registry used by resolution and every language selector."""

    def __init__(
        self,
        languages: tuple[LanguageDefinition, ...],
        *,
        default_language_identifier: str,
    ) -> None:
        """Validate registry identity and deterministic English fallback ownership."""

        if not languages:
            raise ValueError(
                "The language manifest must contain at least one language."
            )
        identifiers = tuple(language.identifier for language in languages)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("The language manifest contains duplicate identifiers.")
        self._languages = languages
        self._default_language = self.language(default_language_identifier)
        if not self._default_language.release_enabled:
            raise ValueError("The default language must be release-enabled.")

    @property
    def languages(self) -> tuple[LanguageDefinition, ...]:
        """Return every validated manifest language in selector order."""

        return self._languages

    @property
    def release_languages(self) -> tuple[LanguageDefinition, ...]:
        """Return the languages that may be selected in production UI."""

        return tuple(
            language for language in self._languages if language.release_enabled
        )

    @property
    def default_language(self) -> LanguageDefinition:
        """Return the deterministic source and fallback language."""

        return self._default_language

    def language(self, identifier: str) -> LanguageDefinition:
        """Return a language by stable identifier or reject unsupported data."""

        for language in self._languages:
            if language.identifier == identifier:
                return language
        raise ValueError(f"Unsupported language identifier: {identifier!r}")


@dataclass(frozen=True, slots=True)
class ResolvedLocale:
    """Separate the durable request from current presentation and formatting state."""

    requested: LanguagePreference
    effective_language: LanguageDefinition
    formatting_locale: str
    matched_ui_language: str | None


__all__ = [
    "LanguageDefinition",
    "FluentCatalogSource",
    "LanguageManifest",
    "LanguagePreference",
    "ResolvedLocale",
    "TextDirection",
]
