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

"""Prepare strict Qt translation delegates from manifest-owned catalog sources."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.localization import LanguageDefinition, ResolvedLocale
from sugarsubstitute_shared.presentation.localization.language_bundle import (
    PreparedLanguageBundle,
)
from sugarsubstitute_shared.presentation.localization.font_profile import (
    localized_application_font,
)

CatalogRole: TypeAlias = Literal["application", "launcher"]
FluentTranslatorFactory: TypeAlias = Callable[[QLocale], QTranslator]


class LanguageResourceLoader(Protocol):
    """Prepare fonts and app-owned snapshots alongside translation catalogs."""

    def prepare(
        self,
        resolved_locale: ResolvedLocale,
        *,
        base_font: QFont,
    ) -> PreparedLanguageBundle:
        """Return a bundle whose translator tuple will be replaced by this loader."""


class QtCatalogBundleLoader:
    """Load app, Fluent, and Qt catalogs in deterministic fallback priority."""

    def __init__(
        self,
        application: QApplication,
        *,
        catalog_role: CatalogRole,
        application_catalog_directory: Path,
        shared_catalog_directory: Path,
        fluent_translator_factory: FluentTranslatorFactory | None,
        resource_loader: LanguageResourceLoader | None = None,
        qt_catalog_directory: Path | None = None,
    ) -> None:
        """Store explicit catalog roots so source and packaged layouts behave alike."""

        self._application = application
        self._base_application_font = QFont(application.font())
        self._catalog_role = catalog_role
        self._application_catalog_directory = application_catalog_directory
        self._shared_catalog_directory = shared_catalog_directory
        self._fluent_translator_factory = fluent_translator_factory
        self._resource_loader = resource_loader
        self._qt_catalog_directory = qt_catalog_directory or Path(
            QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        )

    def prepare(self, resolved_locale: ResolvedLocale) -> PreparedLanguageBundle:
        """Preload all required active catalogs before a visible language change."""

        language = resolved_locale.effective_language
        application_font = localized_application_font(
            self._base_application_font,
            language.font_profile,
        )
        translators: list[QTranslator] = []
        application_catalog_name = _application_catalog_name(
            language,
            role=self._catalog_role,
        )
        if application_catalog_name is not None:
            translators.append(
                _load_file_translator(
                    self._application_catalog_directory / application_catalog_name,
                    catalog_owner=self._catalog_role,
                )
            )
        fluent_translator = self._load_fluent_translator(language)
        if fluent_translator is not None:
            translators.append(fluent_translator)
        if language.qtbase_qm is not None:
            translators.append(
                _load_file_translator(
                    self._qt_catalog_directory / language.qtbase_qm,
                    catalog_owner="Qt",
                )
            )

        if self._resource_loader is None:
            return PreparedLanguageBundle(
                resolved_locale=resolved_locale,
                translators=tuple(translators),
                application_font=application_font,
            )
        resource_bundle = self._resource_loader.prepare(
            resolved_locale,
            base_font=application_font,
        )
        if resource_bundle.resolved_locale != resolved_locale:
            resource_bundle.release()
            raise ValueError("Language resource loader returned a mismatched locale.")
        return PreparedLanguageBundle(
            resolved_locale=resolved_locale,
            translators=tuple(translators),
            application_font=resource_bundle.application_font,
            payload=resource_bundle.payload,
            release_callback=resource_bundle.release,
        )

    def _load_fluent_translator(
        self,
        language: LanguageDefinition,
    ) -> QTranslator | None:
        """Load Fluent text from the manifest-selected upstream or shared owner."""

        source = language.fluent_catalog_source
        if source == "none":
            if language.fluent_qm is not None:
                raise ValueError("A Fluent catalog name requires a catalog source.")
            return None
        if language.fluent_qm is None:
            raise ValueError("A Fluent catalog source requires a catalog name.")
        if source == "shared":
            return _load_file_translator(
                self._shared_catalog_directory / language.fluent_qm,
                catalog_owner="shared Fluent",
            )
        if source == "upstream":
            if self._fluent_translator_factory is None:
                raise RuntimeError("The upstream Fluent translator factory is missing.")
            translator = self._fluent_translator_factory(
                QLocale(language.qt_locale_candidates[0])
            )
            if translator.isEmpty():
                raise RuntimeError(
                    f"The upstream Fluent catalog is empty: {language.fluent_qm}"
                )
            return translator
        raise ValueError(f"Unsupported Fluent catalog source: {source!r}")


def _application_catalog_name(
    language: LanguageDefinition,
    *,
    role: CatalogRole,
) -> str | None:
    """Select app or launcher resources without branching on language identity."""

    if role == "application":
        return language.app_qm
    return language.launcher_qm


def _load_file_translator(path: Path, *, catalog_owner: str) -> QTranslator:
    """Load one required QM and fail before commit when it is missing or empty."""

    translator = QTranslator()
    if not path.is_file() or not translator.load(str(path)) or translator.isEmpty():
        raise RuntimeError(
            f"Required {catalog_owner} translation catalog could not be loaded: {path}"
        )
    return translator


__all__ = [
    "CatalogRole",
    "FluentTranslatorFactory",
    "LanguageResourceLoader",
    "QtCatalogBundleLoader",
]
