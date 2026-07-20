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

"""Compose process-lifetime localization before theme and widget construction."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QLocale, QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.app.bootstrap.application_catalogs import (
    build_application_catalog_loader,
)
from substitute.domain.localization import NodeTextCatalogSnapshot
from substitute.domain.onboarding import ComfyEndpoint, InstallationContext
from substitute.infrastructure.localization.comfy_i18n_client import (
    ComfyI18nCatalogClient,
    ComfyI18nLanguageSelection,
)
from substitute.infrastructure.localization.comfy_frontend_i18n_client import (
    ComfyFrontendI18nClient,
)
from sugarsubstitute_shared.localization import (
    LocalizationPreferenceStore,
    load_language_manifest,
)
from sugarsubstitute_shared.presentation.localization import (
    LanguageSnapshot,
    QFluentFontFamilyAdapter,
    TranslationManager,
    render_application_text,
)


@dataclass(frozen=True, slots=True)
class ApplicationLocalizationRuntime:
    """Retain the process locale owner and its initial committed snapshot."""

    manager: TranslationManager
    initial_snapshot: LanguageSnapshot


@dataclass(frozen=True, slots=True)
class ComfyNodeLocalizationRuntime:
    """Retain the Comfy catalog client and its active-only store."""

    client: ComfyI18nCatalogClient
    store: ActiveComfyNodeCatalogStore


def build_node_presentation_service(
    manager: TranslationManager,
    comfy_store: ActiveComfyNodeCatalogStore,
) -> NodePresentationService:
    """Build node presentation from the active Comfy server generation."""

    def active_snapshot() -> NodeTextCatalogSnapshot:
        """Return the server snapshot matching the committed application locale."""

        return comfy_store.snapshot(manager.snapshot.effective_language_identifier)

    return NodePresentationService(
        active_snapshot,
        application_text_renderer=render_application_text,
    )


class _NodeCatalogRefreshNotifier(QObject):
    """Marshal background catalog publication onto the QApplication thread."""

    refreshRequested = Signal()

    def __init__(self, application: QApplication) -> None:
        """Parent the notifier to the process application for its full lifetime."""

        super().__init__(application)
        self._application = application
        self.refreshRequested.connect(self._dispatch_language_change)

    def notify(self) -> None:
        """Queue a presentation refresh from any background thread."""

        self.refreshRequested.emit()

    @Slot()
    def _dispatch_language_change(self) -> None:
        """Reproject live node cards after a custom catalog generation changes."""

        for widget in self._application.topLevelWidgets():
            self._application.sendEvent(
                widget,
                QEvent(QEvent.Type.LanguageChange),
            )


def build_comfy_node_localization_runtime(
    application: QApplication,
    *,
    manager: TranslationManager,
    endpoint: ComfyEndpoint,
    cache_root: Path,
    background_scheduler: Callable[[Callable[[], None]], object],
) -> ComfyNodeLocalizationRuntime:
    """Compose cached, streamed Comfy catalogs without blocking label lookup."""

    manifest = load_language_manifest()
    store = ActiveComfyNodeCatalogStore()
    notifier = _NodeCatalogRefreshNotifier(application)

    def selection() -> ComfyI18nLanguageSelection:
        """Resolve Comfy aliases from the currently committed manifest language."""

        snapshot = manager.snapshot
        language = manifest.language(snapshot.effective_language_identifier)
        return ComfyI18nLanguageSelection(
            effective_language_identifier=language.identifier,
            comfy_aliases=language.comfy_catalog_aliases,
        )

    client = ComfyI18nCatalogClient(
        endpoint=endpoint,
        cache_root=cache_root,
        language_selection=selection,
        store=store,
        background_scheduler=background_scheduler,
        catalog_published=notifier.notify,
        frontend_node_definitions_loader=(
            ComfyFrontendI18nClient(endpoint).load_node_definitions
        ),
    )
    client.load_cached_selection()
    client.refresh_async()

    def language_changed(snapshot: object) -> None:
        """Release old custom layers and refresh the newly active Comfy alias."""

        if not isinstance(snapshot, LanguageSnapshot):
            return
        store.clear_for_language(snapshot.effective_language_identifier)
        client.refresh_async()

    manager.languageChanged.connect(language_changed)
    return ComfyNodeLocalizationRuntime(client=client, store=store)


def build_application_localization_runtime(
    application: QApplication,
    context: InstallationContext,
    locale_override: str | None,
) -> ApplicationLocalizationRuntime:
    """Install and initialize localization before any app presentation is built."""

    preference_store = LocalizationPreferenceStore(
        context.user_settings_dir / "localization.json"
    )
    bundle_loader = build_application_catalog_loader(application)
    manager = TranslationManager(
        application,
        preference_store=preference_store,
        bundle_loader=bundle_loader,
        ui_languages_provider=lambda: tuple(QLocale.system().uiLanguages()),
        font_adapter=QFluentFontFamilyAdapter(application),
    )
    initial_snapshot = manager.initialize(process_override=locale_override)
    return ApplicationLocalizationRuntime(
        manager=manager,
        initial_snapshot=initial_snapshot,
    )


__all__ = [
    "ApplicationLocalizationRuntime",
    "ComfyNodeLocalizationRuntime",
    "build_application_localization_runtime",
    "build_comfy_node_localization_runtime",
    "build_node_presentation_service",
]
