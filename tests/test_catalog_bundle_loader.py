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

"""Test manifest-driven loading of app, Fluent, and Qt translation catalogs."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.localization import LanguagePreference, resolve_locale
from sugarsubstitute_shared.presentation.localization import QtCatalogBundleLoader

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_english_bundle_uses_source_text_without_translation_delegates() -> None:
    """Keep the deterministic English source fallback resident without a QM."""

    application = _application()
    loader = _application_loader(application)
    resolved = resolve_locale(
        LanguagePreference.explicit("en"),
        ui_languages=("zh-CN",),
    )

    bundle = loader.prepare(resolved)

    assert bundle.translators == ()
    assert bundle.resolved_locale is resolved


def test_chinese_bundle_loads_app_upstream_fluent_and_qt_catalogs() -> None:
    """Load every Chinese delegate in deterministic fallback priority order."""

    application = _application()
    loader = _application_loader(application)
    resolved = resolve_locale(
        LanguagePreference.explicit("zh-Hans"),
        ui_languages=("en-US",),
    )

    bundle = loader.prepare(resolved)

    assert len(bundle.translators) == 3
    assert bundle.application_font.families()[0] == "Microsoft YaHei UI"
    app_catalog, fluent_catalog, qt_catalog = bundle.translators
    assert app_catalog.translate("LanguageSelector", "Language") == "语言"
    assert not fluent_catalog.isEmpty()
    assert qt_catalog.translate("QPlatformTheme", "Cancel") == "取消"


def test_japanese_bundle_loads_app_owned_widget_text_and_qt_catalogs() -> None:
    """Keep Japanese widget-library gaps in the app-owned catalog."""

    application = _application()
    loader = _application_loader(application)
    resolved = resolve_locale(
        LanguagePreference.explicit("ja"),
        ui_languages=("en-US",),
    )

    bundle = loader.prepare(resolved)

    assert len(bundle.translators) == 2
    assert bundle.application_font.families()[0] == "Yu Gothic UI"
    app_catalog, qt_catalog = bundle.translators
    assert app_catalog.translate("LanguageSelector", "Language") == "言語"
    assert app_catalog.translate("SwitchButton", "On") == "オン"
    assert qt_catalog.translate("QPlatformTheme", "Cancel") == "キャンセル"


def test_missing_required_catalog_fails_before_bundle_commit(tmp_path: Path) -> None:
    """Reject an incomplete locale instead of presenting a partially loaded mode."""

    application = _application()
    loader = QtCatalogBundleLoader(
        application,
        catalog_role="application",
        application_catalog_directory=tmp_path,
        shared_catalog_directory=tmp_path,
        fluent_translator_factory=_QrcFluentTranslator,
    )
    resolved = resolve_locale(
        LanguagePreference.explicit("zh-Hans"),
        ui_languages=(),
    )

    try:
        loader.prepare(resolved)
    except RuntimeError as error:
        assert "application translation catalog" in str(error)
    else:
        raise AssertionError("Missing required application catalog was accepted.")


def _application_loader(application: QApplication) -> QtCatalogBundleLoader:
    """Build the source-layout catalog loader used by the application."""

    return QtCatalogBundleLoader(
        application,
        catalog_role="application",
        application_catalog_directory=(
            _PROJECT_ROOT / "substitute" / "presentation" / "resources" / "i18n"
        ),
        shared_catalog_directory=(
            _PROJECT_ROOT / "sugarsubstitute_shared" / "localization" / "resources"
        ),
        fluent_translator_factory=_QrcFluentTranslator,
    )


def _application() -> QApplication:
    """Return the process application used for catalog and font preparation."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


class _QrcFluentTranslator(QTranslator):
    """Load the installed Fluent resource without depending on untyped APIs."""

    def __init__(self, locale: QLocale) -> None:
        """Register qfluentwidgets resources and load the requested catalog."""

        super().__init__()
        importlib.import_module("qfluentwidgets")
        self.load(f":/qfluentwidgets/i18n/qfluentwidgets.{locale.name()}.qm")
