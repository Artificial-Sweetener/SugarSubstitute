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

"""Provide stable test primitives shared by launcher capability suites."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

from launcher.sugarsubstitute_launcher import localization as launcher_localization
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.localization import LanguagePreference, resolve_locale


def launcher_test_application() -> QApplication:
    """Return the shared application instance for launcher-window contracts."""

    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return cast(QApplication, application)


def configure_deterministic_launcher_localization(monkeypatch: MonkeyPatch) -> None:
    """Patch launcher localization composition to use the canonical test locale."""

    resolved = resolve_locale(LanguagePreference.explicit("en"), ui_languages=())
    monkeypatch.setattr(
        launcher_localization,
        "resolve_launcher_locale",
        lambda _layout, *, locale_override: resolved,
    )
    monkeypatch.setattr(
        launcher_localization,
        "build_launcher_localization_runtime",
        lambda _application, **_kwargs: SimpleNamespace(
            manager=object(),
            initial_snapshot=SimpleNamespace(effective_language_identifier="en"),
        ),
    )


def write_launcher_executable(layout: InstallLayout) -> None:
    """Create the target-native launcher executable path for one test layout."""

    layout.executable_path.parent.mkdir(parents=True, exist_ok=True)
    layout.executable_path.write_text("", encoding="utf-8")
