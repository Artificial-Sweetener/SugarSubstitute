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

"""Own process-lifetime locale resolution and atomic live-switch transactions."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.localization import (
    LanguageDefinition,
    LanguageManifest,
    LanguagePreference,
    ResolvedLocale,
    load_language_manifest,
    resolve_locale,
)
from sugarsubstitute_shared.presentation.localization.composite_translator import (
    CompositeTranslator,
)
from sugarsubstitute_shared.presentation.localization.language_bundle import (
    PreparedLanguageBundle,
)

_LOGGER = logging.getLogger("sugarsubstitute.localization.translation_manager")


class LocalizationPreferenceStoreProtocol(Protocol):
    """Load and save the shared durable requested-language value."""

    def load(self) -> LanguagePreference:
        """Load the requested language."""

    def save(self, preference: LanguagePreference) -> None:
        """Persist the requested language atomically."""


class LanguageBundleLoader(Protocol):
    """Prepare every active-only resource before a visible transaction begins."""

    def prepare(self, resolved_locale: ResolvedLocale) -> PreparedLanguageBundle:
        """Return a complete candidate or raise without changing live state."""


class ApplicationFontAdapter(Protocol):
    """Synchronize a presentation library that owns fonts outside QApplication."""

    def snapshot(self) -> object:
        """Return exact adapter state for rollback."""

    def apply_application_font(self, font: QFont) -> None:
        """Apply the active application font profile."""

    def restore(self, state: object) -> None:
        """Restore a previously captured adapter state."""


@dataclass(frozen=True, slots=True)
class LanguageSnapshot:
    """Publish one committed locale revision to non-widget presentation owners."""

    requested: LanguagePreference
    effective_language_identifier: str
    formatting_locale: str
    text_direction: str
    revision: int
    payload: object | None


class TranslationManager(QObject):
    """Coordinate one active locale generation on the QApplication owner thread."""

    languageChanged = Signal(object)

    def __init__(
        self,
        application: QApplication,
        *,
        preference_store: LocalizationPreferenceStoreProtocol,
        bundle_loader: LanguageBundleLoader,
        ui_languages_provider: Callable[[], Sequence[str]],
        manifest: LanguageManifest | None = None,
        font_adapter: ApplicationFontAdapter | None = None,
    ) -> None:
        """Install the one composite translator before any localized widget exists."""

        super().__init__(application)
        self._application = application
        self._preference_store = preference_store
        self._bundle_loader = bundle_loader
        self._ui_languages_provider = ui_languages_provider
        self._manifest = manifest or load_language_manifest()
        self._font_adapter = font_adapter
        self._initial_font_adapter_state = (
            font_adapter.snapshot() if font_adapter is not None else None
        )
        self._composite_translator = CompositeTranslator(parent=self)
        self._active_bundle: PreparedLanguageBundle | None = None
        self._snapshot: LanguageSnapshot | None = None
        self._revision = 0
        self._closed = False
        if not application.installTranslator(self._composite_translator):
            raise RuntimeError("Qt rejected the process localization translator.")
        application.installEventFilter(self)

    @property
    def snapshot(self) -> LanguageSnapshot:
        """Return the committed snapshot after initialization."""

        if self._snapshot is None:
            raise RuntimeError("TranslationManager has not been initialized.")
        return self._snapshot

    @property
    def composite_translator(self) -> CompositeTranslator:
        """Expose active delegate diagnostics without allowing manager replacement."""

        return self._composite_translator

    @property
    def available_languages(self) -> tuple[LanguageDefinition, ...]:
        """Return release-enabled languages in manifest selector order."""

        return self._manifest.release_languages

    def initialize(self, *, process_override: str | None = None) -> LanguageSnapshot:
        """Load the saved request and commit the initial active-only generation."""

        if self._active_bundle is not None:
            raise RuntimeError("TranslationManager is already initialized.")
        return self._switch_language(
            self._preference_store.load(),
            process_override=process_override,
            persist=False,
        )

    def request_language(self, preference: LanguagePreference) -> LanguageSnapshot:
        """Persist and atomically apply a user-selected language without restart."""

        return self._switch_language(preference, process_override=None, persist=True)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Follow machine locale changes only while automatic selection is active."""

        if (
            watched is self._application
            and event.type() == QEvent.Type.LocaleChange
            and self._snapshot is not None
            and self._snapshot.requested.is_system
        ):
            try:
                self._switch_language(
                    self._snapshot.requested,
                    process_override=None,
                    persist=False,
                )
            except (OSError, RuntimeError, ValueError) as error:
                _LOGGER.exception(
                    "Failed to follow a machine locale change; retaining active locale. "
                    "effective_language=%s error=%r",
                    self._snapshot.effective_language_identifier,
                    error,
                )
        return False

    def close(self) -> None:
        """Detach and release the active generation during process teardown."""

        if self._closed:
            return
        self._require_owner_thread()
        self._closed = True
        self._application.removeEventFilter(self)
        self._application.removeTranslator(self._composite_translator)
        self._composite_translator.replace_delegates(())
        if self._active_bundle is not None:
            self._active_bundle.release()
            self._active_bundle = None
        if self._font_adapter is not None:
            self._font_adapter.restore(self._initial_font_adapter_state)

    def _switch_language(
        self,
        preference: LanguagePreference,
        *,
        process_override: str | None,
        persist: bool,
    ) -> LanguageSnapshot:
        """Prepare, persist, commit, notify, and release one locale generation."""

        self._require_owner_thread()
        if self._closed:
            raise RuntimeError("TranslationManager is closed.")
        resolved_locale = resolve_locale(
            preference,
            ui_languages=self._ui_languages_provider(),
            process_override=process_override,
            manifest=self._manifest,
        )
        candidate = self._bundle_loader.prepare(resolved_locale)
        if candidate.resolved_locale != resolved_locale:
            candidate.release()
            raise ValueError("Language bundle loader returned a mismatched locale.")

        previous_preference = (
            self._snapshot.requested
            if self._snapshot is not None
            else self._preference_store.load()
        )
        preference_persisted = False
        try:
            if persist:
                self._preference_store.save(preference)
                preference_persisted = True
            return self._commit_candidate(candidate)
        except (OSError, RuntimeError, ValueError):
            candidate.release()
            if preference_persisted:
                self._restore_preference(previous_preference)
            raise

    def _commit_candidate(
        self,
        candidate: PreparedLanguageBundle,
    ) -> LanguageSnapshot:
        """Swap all Qt-visible state and roll back synchronously on commit failure."""

        previous_bundle = self._active_bundle
        previous_snapshot = self._snapshot
        previous_locale = QLocale()
        previous_font = QFont(self._application.font())
        previous_direction = self._application.layoutDirection()
        previous_delegates = self._composite_translator.delegates
        previous_revision = self._revision
        previous_font_adapter_state = (
            self._font_adapter.snapshot() if self._font_adapter is not None else None
        )
        try:
            self._composite_translator.replace_delegates(candidate.translators)
            QLocale.setDefault(QLocale(candidate.resolved_locale.formatting_locale))
            self._application.setLayoutDirection(
                _qt_layout_direction(
                    candidate.resolved_locale.effective_language.text_direction
                )
            )
            self._application.setFont(candidate.application_font)
            if self._font_adapter is not None:
                self._font_adapter.apply_application_font(candidate.application_font)
            self._active_bundle = candidate
            self._revision += 1
            snapshot = _build_snapshot(candidate, revision=self._revision)
            self._snapshot = snapshot
            for widget in tuple(self._application.topLevelWidgets()):
                QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
            self.languageChanged.emit(snapshot)
        except (RuntimeError, ValueError):
            self._composite_translator.replace_delegates(previous_delegates)
            QLocale.setDefault(previous_locale)
            self._application.setLayoutDirection(previous_direction)
            self._application.setFont(previous_font)
            if self._font_adapter is not None:
                self._font_adapter.restore(previous_font_adapter_state)
            self._active_bundle = previous_bundle
            self._snapshot = previous_snapshot
            self._revision = previous_revision
            raise

        if previous_bundle is not None:
            previous_bundle.release()
        return snapshot

    def _restore_preference(self, preference: LanguagePreference) -> None:
        """Best-effort restore durable state after a post-persistence commit failure."""

        try:
            self._preference_store.save(preference)
        except OSError as error:
            _LOGGER.exception(
                "Failed to restore localization preference after transaction rollback. "
                "requested_language=%s error=%r",
                preference.storage_value,
                error,
            )

    def _require_owner_thread(self) -> None:
        """Reject transactions that could race Qt widget and translator state."""

        if QThread.currentThread() != self.thread():
            raise RuntimeError("Language changes must run on the Qt owner thread.")


def _build_snapshot(
    bundle: PreparedLanguageBundle,
    *,
    revision: int,
) -> LanguageSnapshot:
    """Build the immutable non-widget notification for one committed bundle."""

    resolved = bundle.resolved_locale
    return LanguageSnapshot(
        requested=resolved.requested,
        effective_language_identifier=resolved.effective_language.identifier,
        formatting_locale=resolved.formatting_locale,
        text_direction=resolved.effective_language.text_direction,
        revision=revision,
        payload=bundle.payload,
    )


def _qt_layout_direction(text_direction: str) -> Qt.LayoutDirection:
    """Convert manifest direction data without language-specific branches."""

    if text_direction == "left-to-right":
        return Qt.LayoutDirection.LeftToRight
    if text_direction == "right-to-left":
        return Qt.LayoutDirection.RightToLeft
    raise ValueError(f"Unsupported text direction: {text_direction!r}")


__all__ = [
    "ApplicationFontAdapter",
    "LanguageBundleLoader",
    "LanguageSnapshot",
    "LocalizationPreferenceStoreProtocol",
    "TranslationManager",
]
