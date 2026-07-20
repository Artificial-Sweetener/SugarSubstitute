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

"""Own manifest-backed language selection shared by every Qt executable."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QSignalBlocker
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ComboBox  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import LanguagePreference
from sugarsubstitute_shared.presentation.localization.bindings import (
    LocalizationBindings,
    LocalizedComboItem,
)
from sugarsubstitute_shared.presentation.localization.translation_manager import (
    TranslationManager,
)

LanguageSelectionFailurePresenter = Callable[[str, str], None]

_LOGGER = logging.getLogger("sugarsubstitute.localization.language_selector")
_TRANSLATION_CONTEXT = "LanguageSelector"


class ManifestLanguageComboBox(ComboBox):  # type: ignore[misc]
    """Switch the process locale using stable manifest identifiers."""

    def __init__(
        self,
        manager: TranslationManager,
        *,
        failure_presenter: LanguageSelectionFailurePresenter,
        parent: QWidget | None = None,
    ) -> None:
        """Create a self-updating selector for the process locale owner."""

        super().__init__(parent)
        self._manager = manager
        self._failure_presenter = failure_presenter
        self._changing_language = False
        self._bindings = LocalizationBindings(self)
        self._bindings.bind_combo_items(self, self._combo_items)
        self._bindings.bind_accessible_name(
            self,
            lambda: translate_language_selector("Application language"),
        )
        self._bindings.bind_accessible_description(
            self,
            lambda: translate_language_selector(
                "Select the system language or a supported application language."
            ),
        )
        self._select_requested_language()
        self.currentIndexChanged.connect(self._request_selected_language)
        self._manager.languageChanged.connect(self._on_language_changed)

    def _combo_items(self) -> tuple[LocalizedComboItem, ...]:
        """Build localized labels paired with durable manifest identifiers."""

        effective_language = next(
            language
            for language in self._manager.available_languages
            if language.identifier
            == self._manager.snapshot.effective_language_identifier
        )
        system_label = translate_language_selector("System default — %1").replace(
            "%1",
            effective_language.native_display_name,
        )
        explicit_items = tuple(
            LocalizedComboItem(language.identifier, language.native_display_name)
            for language in self._manager.available_languages
        )
        return (LocalizedComboItem("system", system_label), *explicit_items)

    def _request_selected_language(self, _index: int) -> None:
        """Apply one user selection while preventing overlapping transactions."""

        if self._changing_language:
            return
        selected_identifier = self.currentData()
        if not isinstance(selected_identifier, str):
            return
        current_identifier = self._manager.snapshot.requested.storage_value
        if selected_identifier == current_identifier:
            return
        preference = (
            LanguagePreference.system()
            if selected_identifier == "system"
            else LanguagePreference.explicit(selected_identifier)
        )
        self._changing_language = True
        self.setEnabled(False)
        try:
            self._manager.request_language(preference)
        except (OSError, RuntimeError, ValueError) as error:
            _LOGGER.exception(
                "Failed to change the application language; retaining prior state. "
                "requested_language=%s error=%r",
                preference.storage_value,
                error,
            )
            self._select_requested_language()
            self._failure_presenter(
                translate_language_selector("Failed to change language"),
                translate_language_selector(
                    "SugarSubstitute kept the previous language. %1"
                ).replace("%1", str(error)),
            )
        finally:
            self.setEnabled(True)
            self._changing_language = False

    def _on_language_changed(self, _snapshot: object) -> None:
        """Retranslate options and align selection after a committed generation."""

        self._bindings.retranslate()
        self._select_requested_language()

    def _select_requested_language(self) -> None:
        """Project the committed durable request without emitting a user change."""

        blocker = QSignalBlocker(self)
        requested_identifier = self._manager.snapshot.requested.storage_value
        index = self.findData(requested_identifier)
        if index >= 0:
            self.setCurrentIndex(index)
        del blocker


def translate_language_selector(source_text: str) -> str:
    """Translate one shared language-selector string through active catalogs."""

    return QCoreApplication.translate(_TRANSLATION_CONTEXT, source_text)


__all__ = [
    "LanguageSelectionFailurePresenter",
    "ManifestLanguageComboBox",
    "translate_language_selector",
]
