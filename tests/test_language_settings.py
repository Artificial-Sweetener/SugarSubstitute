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

"""Test the live manifest-backed application-language Settings control."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.localization_composition import (
    build_application_localization_runtime,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.presentation.settings.language_settings import LanguageSettingsCard
from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
    ResolvedLocale,
)
from sugarsubstitute_shared.presentation.localization import (
    PreparedLanguageBundle,
    TranslationManager,
)


def test_language_settings_switches_catalogs_and_persists_without_restart(
    tmp_path: Path,
) -> None:
    """Apply Chinese then Japanese while retaining only the active generation."""

    application = _application()
    context = _context(tmp_path)
    preference_path = context.user_settings_dir / "localization.json"
    store = LocalizationPreferenceStore(preference_path)
    store.save(LanguagePreference.explicit("en"))
    runtime = build_application_localization_runtime(application, context, None)
    card = LanguageSettingsCard(runtime.manager)

    assert tuple(
        card.language_combo.itemData(index)
        for index in range(card.language_combo.count())
    ) == ("system", "en", "zh-Hans", "ja")
    assert card.language_combo.itemText(0) == "System default — English"
    assert card.language_combo.itemText(2) == "简体中文"
    assert card.language_combo.itemText(3) == "日本語"

    card.language_combo.setCurrentIndex(card.language_combo.findData("zh-Hans"))
    chinese_delegates = runtime.manager.composite_translator.delegates

    assert runtime.manager.snapshot.requested == LanguagePreference.explicit("zh-Hans")
    assert store.load() == LanguagePreference.explicit("zh-Hans")
    assert card.title_label.text() == "语言"
    assert "更改会立即生效" in card.description_label.text()
    assert QCoreApplication.translate("LanguageSelector", "Language") == "语言"
    assert card.language_combo.isEnabled()

    card.language_combo.setCurrentIndex(card.language_combo.findData("ja"))

    assert runtime.manager.snapshot.requested == LanguagePreference.explicit("ja")
    assert store.load() == LanguagePreference.explicit("ja")
    assert card.title_label.text() == "言語"
    assert "変更はすぐに反映されます" in card.description_label.text()
    assert QCoreApplication.translate("LanguageSelector", "Language") == "言語"
    assert all(
        delegate not in runtime.manager.composite_translator.delegates
        for delegate in chinese_delegates
    )

    card.close()
    runtime.manager.close()


def test_language_settings_restores_committed_selection_when_switch_fails() -> None:
    """Keep the prior request selected and re-enable input after preparation failure."""

    application = _application()
    store = _MemoryPreferenceStore(LanguagePreference.explicit("en"))
    manager = TranslationManager(
        application,
        preference_store=store,
        bundle_loader=_FailingBundleLoader(application),
        ui_languages_provider=lambda: ("en-US",),
    )
    manager.initialize()
    failures: list[tuple[str, str]] = []
    card = LanguageSettingsCard(
        manager,
        failure_presenter=lambda title, content: failures.append((title, content)),
    )

    card.language_combo.setCurrentIndex(card.language_combo.findData("zh-Hans"))

    assert manager.snapshot.requested == LanguagePreference.explicit("en")
    assert card.language_combo.currentData() == "en"
    assert card.language_combo.isEnabled()
    assert failures[0][0] == "Failed to change language"
    assert "catalog unavailable" in failures[0][1]
    card.close()
    manager.close()


class _MemoryPreferenceStore:
    """Retain one preference for transaction failure coverage."""

    def __init__(self, preference: LanguagePreference) -> None:
        """Store the initial durable request."""

        self.preference = preference

    def load(self) -> LanguagePreference:
        """Return the current durable request."""

        return self.preference

    def save(self, preference: LanguagePreference) -> None:
        """Replace the current durable request."""

        self.preference = preference


class _FailingBundleLoader:
    """Prepare English and reject Chinese before a transaction can commit."""

    def __init__(self, application: QApplication) -> None:
        """Retain the source application font."""

        self._application = application

    def prepare(self, resolved_locale: ResolvedLocale) -> PreparedLanguageBundle:
        """Return an English bundle or simulate a missing requested catalog."""

        if resolved_locale.effective_language.identifier == "zh-Hans":
            raise OSError("catalog unavailable")
        return PreparedLanguageBundle(
            resolved_locale=resolved_locale,
            translators=(),
            application_font=QFont(self._application.font()),
        )


def test_translation_manager_exposes_only_release_enabled_manifest_languages(
    tmp_path: Path,
) -> None:
    """Drive every selector from the manager's validated release manifest."""

    application = _application()
    context = _context(tmp_path)
    runtime = build_application_localization_runtime(application, context, "en")

    assert tuple(
        language.identifier for language in runtime.manager.available_languages
    ) == ("en", "zh-Hans", "ja")
    runtime.manager.close()


def _application() -> QApplication:
    """Return the process application used by localization presentation tests."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def _context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic remote-mode installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )
