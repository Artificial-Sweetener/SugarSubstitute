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

"""Test atomic active-only language transactions and automatic locale following."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from sugarsubstitute_shared.localization import (
    LanguagePreference,
    ResolvedLocale,
)
from sugarsubstitute_shared.presentation.localization import (
    LocalizationBindings,
    PreparedLanguageBundle,
    TranslationManager,
)


def test_manager_initializes_before_widgets_and_switches_active_generation() -> None:
    """Publish complete language bundles while releasing only the detached locale."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.system())
    ui_languages = ["zh-CN"]
    loader = _RecordingBundleLoader(application)
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: tuple(ui_languages),
    )
    snapshots: list[object] = []
    manager.languageChanged.connect(snapshots.append)

    initial = manager.initialize()

    assert initial.requested == LanguagePreference.system()
    assert initial.effective_language_identifier == "zh-Hans"
    assert initial.revision == 1
    assert QCoreApplication.translate("Test", "Greeting") == "你好"
    assert len(loader.bundles) == 1
    assert loader.bundles[0].released is False

    switched = manager.request_language(LanguagePreference.explicit("ja"))

    assert switched.effective_language_identifier == "ja"
    assert switched.revision == 2
    assert store.preference == LanguagePreference.explicit("ja")
    assert QCoreApplication.translate("Test", "Greeting") == "こんにちは"
    assert loader.bundles[0].released is True
    assert loader.bundles[1].released is False
    assert manager.composite_translator.delegates == loader.bundles[1].translators
    assert snapshots == [initial, switched]
    manager.close()
    assert loader.bundles[1].released is True


def test_manager_language_change_refreshes_open_widget_without_losing_state() -> None:
    """Retranslate one mounted tree in place during the transaction."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.explicit("en"))
    loader = _RecordingBundleLoader(application)
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: ("en-US",),
    )
    manager.initialize()
    window = QWidget()
    label = QLabel(window)
    bindings = LocalizationBindings(window)
    bindings.bind_text(
        label,
        lambda: QCoreApplication.translate("Test", "Greeting"),
    )
    window.show()
    application.processEvents()

    manager.request_language(LanguagePreference.explicit("zh-Hans"))

    assert label.text() == "你好"
    assert window.isVisible()
    window.close()
    window.deleteLater()
    manager.close()


def test_manager_preload_failure_keeps_persisted_and_visible_language() -> None:
    """Abort before persistence when a complete candidate cannot be prepared."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.explicit("en"))
    loader = _RecordingBundleLoader(application)
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: ("en-US",),
    )
    original = manager.initialize()
    loader.fail_language = "ja"

    with pytest.raises(RuntimeError, match="prepare failed"):
        manager.request_language(LanguagePreference.explicit("ja"))

    assert manager.snapshot is original
    assert store.preference == LanguagePreference.explicit("en")
    assert QCoreApplication.translate("Test", "Greeting") == "Hello"
    assert loader.bundles[0].released is False
    manager.close()


def test_manager_persistence_failure_releases_candidate_without_commit() -> None:
    """Dispose a preloaded generation when the durable request cannot be saved."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.explicit("en"))
    loader = _RecordingBundleLoader(application)
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: ("en-US",),
    )
    original = manager.initialize()
    store.fail_save = True

    with pytest.raises(OSError, match="save failed"):
        manager.request_language(LanguagePreference.explicit("ja"))

    assert manager.snapshot is original
    assert loader.bundles[0].released is False
    assert loader.bundles[1].released is True
    assert QCoreApplication.translate("Test", "Greeting") == "Hello"
    manager.close()


def test_manager_follows_locale_change_only_in_system_mode() -> None:
    """Re-resolve automatic selection while leaving explicit choices stable."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.system())
    ui_languages = ["en-US"]
    loader = _RecordingBundleLoader(application)
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: tuple(ui_languages),
    )
    manager.initialize()

    ui_languages[:] = ["ja-JP"]
    QCoreApplication.sendEvent(application, QEvent(QEvent.Type.LocaleChange))

    assert manager.snapshot.effective_language_identifier == "ja"
    assert manager.snapshot.requested.is_system
    assert store.save_calls == []

    manager.request_language(LanguagePreference.explicit("zh-Hans"))
    revision = manager.snapshot.revision
    ui_languages[:] = ["en-US"]
    QCoreApplication.sendEvent(application, QEvent(QEvent.Type.LocaleChange))

    assert manager.snapshot.effective_language_identifier == "zh-Hans"
    assert manager.snapshot.revision == revision
    manager.close()


def test_manager_switches_and_restores_external_font_owner_atomically() -> None:
    """Keep QFluent-style font state aligned through switch, rollback, and close."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.explicit("en"))
    loader = _RecordingBundleLoader(application)
    font_adapter = _RecordingFontAdapter(("Library Default",))
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=loader,
        ui_languages_provider=lambda: ("en-US",),
        font_adapter=font_adapter,
    )

    initial = manager.initialize()

    assert initial.revision == 1
    assert font_adapter.state == ("Test en",)

    switched = manager.request_language(LanguagePreference.explicit("ja"))

    assert switched.revision == 2
    assert font_adapter.state == ("Test ja",)

    font_adapter.fail_next_apply = True
    with pytest.raises(RuntimeError, match="font apply failed"):
        manager.request_language(LanguagePreference.explicit("zh-Hans"))

    assert manager.snapshot is switched
    assert manager.snapshot.revision == 2
    assert font_adapter.state == ("Test ja",)
    manager.close()
    assert font_adapter.state == ("Library Default",)


def _application() -> QApplication:
    """Return the process application required by translation transactions."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


class _MemoryPreferenceStore:
    """Persist language requests in memory while exposing failure boundaries."""

    def __init__(self, preference: LanguagePreference) -> None:
        """Store the initial requested language."""

        self.preference = preference
        self.fail_save = False
        self.save_calls: list[LanguagePreference] = []

    def load(self) -> LanguagePreference:
        """Return the current durable request."""

        return self.preference

    def save(self, preference: LanguagePreference) -> None:
        """Record or reject one atomic preference update."""

        if self.fail_save:
            raise OSError("save failed")
        self.save_calls.append(preference)
        self.preference = preference


class _RecordingBundleLoader:
    """Prepare translated generations without external catalog files."""

    def __init__(self, application: QApplication) -> None:
        """Use the current application font for deterministic bundle state."""

        self._application = application
        self.bundles: list[PreparedLanguageBundle] = []
        self.fail_language: str | None = None

    def prepare(self, resolved_locale: ResolvedLocale) -> PreparedLanguageBundle:
        """Return one translated generation or simulate a preload failure."""

        identifier = resolved_locale.effective_language.identifier
        if identifier == self.fail_language:
            raise RuntimeError("prepare failed")
        translations = {
            "en": "Hello",
            "zh-Hans": "你好",
            "ja": "こんにちは",
        }
        application_font = QFont(self._application.font())
        application_font.setFamilies([f"Test {identifier}"])
        bundle = PreparedLanguageBundle(
            resolved_locale=resolved_locale,
            translators=(
                _DictionaryTranslator({("Test", "Greeting"): translations[identifier]}),
            ),
            application_font=application_font,
            payload={"language": identifier},
        )
        self.bundles.append(bundle)
        return bundle


class _DictionaryTranslator(QTranslator):
    """Return deterministic context/source translations for manager tests."""

    def __init__(self, translations: dict[tuple[str, str], str]) -> None:
        """Store the generation's active translations."""

        super().__init__()
        self._translations = translations

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Return a mapped translation while ignoring unused plural metadata."""

        del disambiguation, n
        return self._translations.get((context, source_text), "")


class _RecordingFontAdapter:
    """Model a library-owned global font list with one injected failure."""

    def __init__(self, state: tuple[str, ...]) -> None:
        """Store the exact initial state."""

        self.state = state
        self.fail_next_apply = False

    def snapshot(self) -> object:
        """Return the current state."""

        return self.state

    def apply_application_font(self, font: QFont) -> None:
        """Apply families before optionally failing to exercise rollback."""

        self.state = tuple(font.families())
        if self.fail_next_apply:
            self.fail_next_apply = False
            raise RuntimeError("font apply failed")

    def restore(self, state: object) -> None:
        """Restore one previously captured tuple."""

        if not isinstance(state, tuple):
            raise ValueError("invalid font state")
        self.state = cast(tuple[str, ...], state)
