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

"""Enforce complete authored and runtime catalogs for every release locale."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from sugarsubstitute_shared.localization import (
    LanguageDefinition,
    LanguageManifest,
    load_language_manifest,
)
from tools.check_translations import translation_coverage_failures

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_release_locale_has_absolute_translation_coverage() -> None:
    """All registered locales must match owned sources and shipped QM content."""

    failures = translation_coverage_failures(_PROJECT_ROOT)

    assert failures == (), "\n".join(failures)


def test_new_release_locale_automatically_requires_every_catalog_domain() -> None:
    """Adding a manifest locale must require app and launcher catalogs."""

    manifest = load_language_manifest()
    french = replace(
        manifest.default_language,
        identifier="fr",
        native_display_name="Français",
        qt_locale_candidates=("fr_FR", "fr"),
        accepted_system_tags=("fr", "fr-*"),
        comfy_catalog_aliases=("fr",),
        app_qm="sugarsubstitute_fr_FR.qm",
        launcher_qm="launcher_fr_FR.qm",
    )
    expanded_manifest = LanguageManifest(
        (*manifest.languages, french),
        default_language_identifier=manifest.default_language.identifier,
    )

    failures = translation_coverage_failures(
        _PROJECT_ROOT,
        manifest=expanded_manifest,
        validate_compiled_catalogs=False,
    )

    assert "fr:app: missing app_fr_FR.ts" in failures
    assert "fr:launcher: missing launcher_fr_FR.ts" in failures


def test_new_owned_source_automatically_requires_every_existing_locale(
    tmp_path: Path,
) -> None:
    """Adding owned UI copy must make an incomplete existing locale fail."""

    source_root = tmp_path / "substitute" / "presentation"
    source_root.mkdir(parents=True)
    (source_root / "new_feature.py").write_text(
        "app_text('Existing message')\napp_text('New message')\n",
        encoding="utf-8",
    )
    translations_root = tmp_path / "translations"
    translations_root.mkdir()
    _write_catalog(
        translations_root / "app_zh_CN.ts",
        language="zh_CN",
        context="AppText",
        source="Existing message",
        translation="现有消息",
    )
    _write_catalog(
        translations_root / "launcher_zh_CN.ts",
        language="zh_CN",
        context="LauncherMainWindow",
        source=None,
        translation=None,
    )

    failures = translation_coverage_failures(
        tmp_path,
        manifest=_minimal_manifest(),
        validate_compiled_catalogs=False,
    )

    assert "app_zh_CN.ts: missing: AppText:New message" in failures


def _minimal_manifest() -> LanguageManifest:
    """Return an English-source registry with one translated release locale."""

    english = _language("en", "en_US", app_qm=None, launcher_qm=None)
    chinese = _language(
        "zh-Hans",
        "zh_CN",
        app_qm="sugarsubstitute_zh_CN.qm",
        launcher_qm="launcher_zh_CN.qm",
    )
    return LanguageManifest(
        (english, chinese),
        default_language_identifier=english.identifier,
    )


def _language(
    identifier: str,
    qt_locale: str,
    *,
    app_qm: str | None,
    launcher_qm: str | None,
) -> LanguageDefinition:
    """Build one compact release language for registry behavior tests."""

    return LanguageDefinition(
        identifier=identifier,
        native_display_name=identifier,
        qt_locale_candidates=(qt_locale,),
        accepted_system_tags=(identifier,),
        comfy_catalog_aliases=(identifier,),
        app_qm=app_qm,
        launcher_qm=launcher_qm,
        qtbase_qm=None,
        fluent_qm=None,
        fluent_catalog_source="none",
        text_direction="left-to-right",
        font_profile="system",
        release_enabled=True,
    )


def _write_catalog(
    path: Path,
    *,
    language: str,
    context: str,
    source: str | None,
    translation: str | None,
) -> None:
    """Write one minimal Qt source catalog for coverage behavior tests."""

    message = ""
    if source is not None and translation is not None:
        message = (
            f"<message><source>{source}</source>"
            f"<translation>{translation}</translation></message>"
        )
    path.write_text(
        f'<TS version="2.1" language="{language}" sourcelanguage="en_US">'
        f"<context><name>{context}</name>{message}</context></TS>",
        encoding="utf-8",
    )
