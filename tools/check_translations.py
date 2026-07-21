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

"""Validate absolute translation coverage for every production locale."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QTranslator

from sugarsubstitute_shared.localization import LanguageManifest, load_language_manifest
from tools.localization_catalog import (
    extract_application_messages,
    extract_language_selector_messages,
    extract_launcher_messages,
    placeholders,
)
from tools.translation_catalog_registry import (
    TranslationCatalogArtifact,
    TranslationDomain,
    release_translation_catalogs,
)

CatalogKey = tuple[str, str]

_APP_CONTEXT = "AppText"
_LANGUAGE_SELECTOR_CONTEXT = "LanguageSelector"
_LAUNCHER_CONTEXT = "LauncherMainWindow"
_IDENTITY_ALLOWED = frozenset(
    {
        "ComfyUI",
        "PySide6",
        "PySide6-Fluent-Widgets",
        "QPane",
        "Qt for Python",
        "Python: %1",
        "Sugar-DSL",
        "Sugar Substitute",
        "SugarCubes",
        "SugarSubstitute",
        "TAESD",
        "https://github.com/owner/repository",
    }
)
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_STRICT_SOURCE_CONTEXTS = {
    TranslationDomain.APPLICATION: frozenset({_APP_CONTEXT}),
    TranslationDomain.LAUNCHER: frozenset({_LAUNCHER_CONTEXT}),
}


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Store one authored translation and its completion state."""

    translation: str
    unfinished: bool


@dataclass(frozen=True, slots=True)
class TranslationCatalog:
    """Store one parsed Qt catalog and structural diagnostics."""

    language: str
    entries: dict[CatalogKey, CatalogEntry]
    duplicate_keys: tuple[CatalogKey, ...]


def translation_coverage_failures(
    project_root: Path,
    *,
    manifest: LanguageManifest | None = None,
    validate_compiled_catalogs: bool = True,
) -> tuple[str, ...]:
    """Return every source, locale, and runtime catalog parity failure."""

    active_manifest = manifest or load_language_manifest()
    try:
        artifacts = release_translation_catalogs(
            project_root,
            manifest=active_manifest,
        )
    except ValueError as error:
        return (str(error),)

    expected_by_domain = _expected_owned_messages(project_root)
    failures: list[str] = []
    for domain in TranslationDomain:
        domain_artifacts = tuple(
            artifact for artifact in artifacts if artifact.domain is domain
        )
        catalogs: list[tuple[TranslationCatalogArtifact, TranslationCatalog]] = []
        for artifact in domain_artifacts:
            catalog, read_failures = _read_release_catalog(artifact)
            failures.extend(read_failures)
            if catalog is not None:
                catalogs.append((artifact, catalog))
        failures.extend(
            _validate_domain_catalogs(
                domain,
                catalogs,
                expected_owned=expected_by_domain[domain],
                validate_compiled_catalogs=validate_compiled_catalogs,
            )
        )
    return tuple(failures)


def main() -> int:
    """Report incomplete locale coverage and stale runtime catalogs."""

    project_root = Path(__file__).resolve().parents[1]
    failures = translation_coverage_failures(project_root)
    if failures:
        print("\n".join(failures))
        return 1
    manifest = load_language_manifest()
    translated_locale_count = len(manifest.release_languages) - 1
    message_count = len(extract_application_messages(project_root))
    print(
        f"Validated {message_count} AppText messages across "
        f"{translated_locale_count} translated release locales."
    )
    return 0


def _expected_owned_messages(
    project_root: Path,
) -> dict[TranslationDomain, frozenset[CatalogKey]]:
    """Extract canonical English messages for every app-owned Qt context."""

    application = {
        *(
            (_APP_CONTEXT, message.source)
            for message in extract_application_messages(project_root)
        ),
        *(
            (_LANGUAGE_SELECTOR_CONTEXT, message.source)
            for message in extract_language_selector_messages(project_root)
        ),
    }
    launcher = {
        (_LAUNCHER_CONTEXT, message.source)
        for message in extract_launcher_messages(project_root)
    }
    return {
        TranslationDomain.APPLICATION: frozenset(application),
        TranslationDomain.LAUNCHER: frozenset(launcher),
    }


def _read_release_catalog(
    artifact: TranslationCatalogArtifact,
) -> tuple[TranslationCatalog | None, tuple[str, ...]]:
    """Read one required source catalog and validate its declared locale."""

    path = artifact.source_path
    if not path.is_file():
        return None, (
            f"{artifact.language.identifier}:{artifact.domain.value}: missing {path.name}",
        )
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        return None, (f"{path.name}: unreadable Qt catalog: {error}",)
    language = root.get("language", "")
    accepted_languages = {
        _normalized_qt_locale(candidate)
        for candidate in artifact.language.qt_locale_candidates
    }
    failures: list[str] = []
    if _normalized_qt_locale(language) not in accepted_languages:
        failures.append(
            f"{path.name}: catalog language {language!r} does not match "
            f"{artifact.language.identifier}"
        )
    entries: dict[CatalogKey, CatalogEntry] = {}
    duplicate_keys: list[CatalogKey] = []
    for context in root.findall("context"):
        context_name = context.findtext("name") or ""
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            key = (context_name, source)
            if key in entries:
                duplicate_keys.append(key)
            translation = message.find("translation")
            translation_text = (
                "" if translation is None else "".join(translation.itertext())
            )
            translation_type = (
                "unfinished" if translation is None else translation.get("type", "")
            )
            entries[key] = CatalogEntry(
                translation=translation_text,
                unfinished=translation_type in {"unfinished", "vanished", "obsolete"},
            )
    return (
        TranslationCatalog(
            language=language,
            entries=entries,
            duplicate_keys=tuple(sorted(set(duplicate_keys))),
        ),
        tuple(failures),
    )


def _validate_domain_catalogs(
    domain: TranslationDomain,
    catalogs: list[tuple[TranslationCatalogArtifact, TranslationCatalog]],
    *,
    expected_owned: frozenset[CatalogKey],
    validate_compiled_catalogs: bool,
) -> tuple[str, ...]:
    """Require exact owned coverage and parity for framework-owned contexts."""

    strict_source_contexts = _STRICT_SOURCE_CONTEXTS[domain]
    external_required = frozenset(
        key
        for _artifact, catalog in catalogs
        for key in catalog.entries
        if key[0] not in strict_source_contexts
    )
    required = expected_owned | external_required
    failures: list[str] = []
    for artifact, catalog in catalogs:
        filename = artifact.source_path.name
        actual = frozenset(catalog.entries)
        failures.extend(
            f"{filename}: missing: {_message_label(key)}"
            for key in sorted(required - actual)
        )
        failures.extend(
            f"{filename}: stale: {_message_label(key)}"
            for key in sorted(actual - expected_owned)
            if key[0] in strict_source_contexts
        )
        failures.extend(
            f"{filename}: duplicate: {_message_label(key)}"
            for key in catalog.duplicate_keys
        )
        failures.extend(_entry_failures(filename, catalog.entries))
        if validate_compiled_catalogs:
            failures.extend(_compiled_catalog_failures(artifact, catalog.entries))
    return tuple(failures)


def _entry_failures(
    filename: str,
    entries: dict[CatalogKey, CatalogEntry],
) -> tuple[str, ...]:
    """Validate completion, placeholders, and accidental English copies."""

    failures: list[str] = []
    for key, entry in sorted(entries.items()):
        source = key[1]
        label = f"{filename}:{_message_label(key)}"
        if entry.unfinished or not entry.translation.strip():
            failures.append(f"{label}: unfinished")
        elif sorted(placeholders(source)) != sorted(placeholders(entry.translation)):
            failures.append(f"{label}: placeholder mismatch")
        elif (
            source == entry.translation
            and _LATIN_LETTER.search(source)
            and source not in _IDENTITY_ALLOWED
        ):
            failures.append(f"{label}: untranslated")
    return tuple(failures)


def _compiled_catalog_failures(
    artifact: TranslationCatalogArtifact,
    entries: dict[CatalogKey, CatalogEntry],
) -> tuple[str, ...]:
    """Require the shipped QM to contain every exact authored translation."""

    translator = QTranslator()
    if not translator.load(str(artifact.compiled_path)):
        return (
            f"{artifact.language.identifier}:{artifact.domain.value}: missing or "
            f"invalid runtime catalog {artifact.compiled_path.name}",
        )
    failures: list[str] = []
    for (context, source), entry in sorted(entries.items()):
        runtime_translation = translator.translate(context, source)
        if runtime_translation != entry.translation:
            failures.append(
                f"{artifact.compiled_path.name}: stale runtime translation: "
                f"{_message_label((context, source))}"
            )
    return tuple(failures)


def _normalized_qt_locale(locale_name: str) -> str:
    """Normalize Qt and BCP-47 separators for catalog identity checks."""

    return locale_name.replace("-", "_").casefold()


def _message_label(key: CatalogKey) -> str:
    """Render one context-qualified source for actionable failures."""

    return f"{key[0]}:{key[1]}"


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["translation_coverage_failures"]
