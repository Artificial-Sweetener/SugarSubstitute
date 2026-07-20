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

"""Resolve and compose localization for setup, repair, and app handoff."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
    ResolvedLocale,
    resolve_locale,
)

if TYPE_CHECKING:
    from PySide6.QtCore import QLocale, QTranslator
    from PySide6.QtWidgets import QApplication

    from sugarsubstitute_shared.presentation.localization import (
        LanguageSnapshot,
        TranslationManager,
    )


@dataclass(frozen=True, slots=True)
class LauncherLocalizationRuntime:
    """Retain the launcher locale owner and its initial committed snapshot."""

    manager: TranslationManager
    initial_snapshot: LanguageSnapshot


def resolve_launcher_locale(
    layout: InstallLayout,
    *,
    locale_override: str | None,
) -> ResolvedLocale:
    """Resolve GUI and handoff language before a QApplication is required."""

    from PySide6.QtCore import QLocale

    preference = _preference_store(layout).load()
    return resolve_locale(
        preference,
        ui_languages=tuple(QLocale.system().uiLanguages()),
        process_override=locale_override,
    )


def build_launcher_localization_runtime(
    application: QApplication,
    *,
    layout: InstallLayout,
    locale_override: str | None,
) -> LauncherLocalizationRuntime:
    """Install launcher translators before importing or constructing its window."""

    from PySide6.QtCore import QLocale

    from sugarsubstitute_shared.presentation.localization import (
        QtCatalogBundleLoader,
        QFluentFontFamilyAdapter,
        TranslationManager,
    )

    package_root = Path(__file__).resolve().parent
    project_root = package_root.parents[1]
    manager = TranslationManager(
        application,
        preference_store=_preference_store(layout),
        bundle_loader=QtCatalogBundleLoader(
            application,
            catalog_role="launcher",
            application_catalog_directory=package_root / "i18n",
            shared_catalog_directory=(
                project_root / "sugarsubstitute_shared" / "localization" / "resources"
            ),
            fluent_translator_factory=_load_upstream_fluent_translator,
        ),
        ui_languages_provider=lambda: tuple(QLocale.system().uiLanguages()),
        font_adapter=QFluentFontFamilyAdapter(application),
    )
    initial_snapshot = manager.initialize(process_override=locale_override)
    return LauncherLocalizationRuntime(
        manager=manager,
        initial_snapshot=initial_snapshot,
    )


def seed_headless_locale_preference(
    layout: InstallLayout,
    *,
    locale_override: str | None,
) -> None:
    """Persist an explicit headless locale after installation succeeds."""

    if locale_override is None:
        return
    _preference_store(layout).save(LanguagePreference.explicit(locale_override))


def _preference_store(layout: InstallLayout) -> LocalizationPreferenceStore:
    """Return the one durable preference store shared with the installed app."""

    return LocalizationPreferenceStore.for_install_root(layout.root)


def _load_upstream_fluent_translator(locale: QLocale) -> QTranslator:
    """Load QFluent's registered resource through a typed Qt-only adapter."""

    from PySide6.QtCore import QTranslator

    importlib.import_module("qfluentwidgets")
    translator = QTranslator()
    translator.load(f":/qfluentwidgets/i18n/qfluentwidgets.{locale.name()}.qm")
    return translator


__all__ = [
    "LauncherLocalizationRuntime",
    "build_launcher_localization_runtime",
    "resolve_launcher_locale",
    "seed_headless_locale_preference",
]
