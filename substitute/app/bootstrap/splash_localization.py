#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Install application catalogs in the isolated early splash host process."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.application_catalogs import (
    build_application_catalog_loader,
)
from sugarsubstitute_shared.localization import LanguagePreference
from sugarsubstitute_shared.presentation.localization import (
    LanguageSnapshot,
    QFluentFontFamilyAdapter,
    TranslationManager,
)


@dataclass(frozen=True, slots=True)
class SplashLocalizationRuntime:
    """Retain the locale owner for the full splash-host process lifetime."""

    manager: TranslationManager
    initial_snapshot: LanguageSnapshot


def build_splash_localization_runtime(
    application: QApplication,
    *,
    locale_override: str,
) -> SplashLocalizationRuntime:
    """Install the effective handoff locale before constructing the splash window."""

    manager = TranslationManager(
        application,
        preference_store=_ProcessPreferenceStore(),
        bundle_loader=build_application_catalog_loader(application),
        ui_languages_provider=lambda: tuple(QLocale.system().uiLanguages()),
        font_adapter=QFluentFontFamilyAdapter(application),
    )
    initial_snapshot = manager.initialize(process_override=locale_override)
    return SplashLocalizationRuntime(
        manager=manager,
        initial_snapshot=initial_snapshot,
    )


class _ProcessPreferenceStore:
    """Provide automatic intent to a helper that never owns durable settings."""

    def load(self) -> LanguagePreference:
        """Return automatic intent while the effective handoff remains process-only."""

        return LanguagePreference.system()

    def save(self, preference: LanguagePreference) -> None:
        """Reject persistence because the parent executable owns user settings."""

        del preference
        raise RuntimeError("The splash host cannot persist language preferences.")


__all__ = ["SplashLocalizationRuntime", "build_splash_localization_runtime"]
