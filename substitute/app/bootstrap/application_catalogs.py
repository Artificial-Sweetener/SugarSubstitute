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

"""Own source and packaged paths for SugarSubstitute application catalogs."""

from __future__ import annotations

import importlib
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.presentation.localization import QtCatalogBundleLoader


def build_application_catalog_loader(
    application: QApplication,
) -> QtCatalogBundleLoader:
    """Build the app catalog loader for source and unchanged payload layouts."""

    substitute_root = Path(__file__).resolve().parents[2]
    project_root = substitute_root.parent
    return QtCatalogBundleLoader(
        application,
        catalog_role="application",
        application_catalog_directory=(
            substitute_root / "presentation" / "resources" / "i18n"
        ),
        shared_catalog_directory=(
            project_root / "sugarsubstitute_shared" / "localization" / "resources"
        ),
        fluent_translator_factory=load_upstream_fluent_translator,
    )


def load_upstream_fluent_translator(locale: QLocale) -> QTranslator:
    """Load QFluent's registered resource through a typed Qt-only adapter."""

    importlib.import_module("qfluentwidgets")
    translator = QTranslator()
    translator.load(f":/qfluentwidgets/i18n/qfluentwidgets.{locale.name()}.qm")
    return translator


__all__ = ["build_application_catalog_loader", "load_upstream_fluent_translator"]
