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

"""Test the Qt-free localization contract shared by every executable."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
    format_locale_argument,
    load_language_manifest,
    normalize_locale_tag,
    parse_locale_override,
    resolve_locale,
)


def test_language_manifest_defines_release_languages_as_data() -> None:
    """Load all initial release languages from the packaged manifest."""

    manifest = load_language_manifest()

    assert tuple(language.identifier for language in manifest.release_languages) == (
        "en",
        "zh-Hans",
        "ja",
    )
    assert tuple(
        language.native_display_name for language in manifest.release_languages
    ) == ("English", "简体中文", "日本語")
    assert manifest.default_language.identifier == "en"
    assert manifest.language("zh-Hans").comfy_catalog_aliases == ("zh", "zh-CN")
    assert manifest.language("ja").font_profile == "cjk-jp"


@pytest.mark.parametrize(
    ("raw_tag", "expected"),
    [
        ("EN_us", "en-US"),
        ("zh_hans_cn", "zh-Hans-CN"),
        ("ja-JP", "ja-JP"),
        ("pt_br", "pt-BR"),
        ("en_US.UTF-8", "en-US"),
        ("", None),
        ("not a locale", None),
        ("x", None),
    ],
)
def test_normalize_locale_tag_canonicalizes_platform_variants(
    raw_tag: str,
    expected: str | None,
) -> None:
    """Normalize common platform spellings without depending on Qt."""

    assert normalize_locale_tag(raw_tag) == expected


@pytest.mark.parametrize(
    ("ui_languages", "expected_language", "expected_formatting_locale"),
    [
        (("ja-JP", "en-US"), "ja", "ja-JP"),
        (("zh_CN", "en-US"), "zh-Hans", "zh-CN"),
        (("zh-Hans-SG",), "zh-Hans", "zh-Hans-SG"),
        (("zh",), "zh-Hans", "zh-CN"),
        (("zh-TW",), "en", "en-TW"),
        (("zh-Hant-HK",), "en", "en-HK"),
        (("de-DE",), "en", "en-DE"),
        (("de",), "en", "en-US"),
        ((), "en", "en-US"),
    ],
)
def test_system_locale_resolution_is_ordered_and_uses_english_fallback(
    ui_languages: tuple[str, ...],
    expected_language: str,
    expected_formatting_locale: str,
) -> None:
    """Resolve supported machine UI languages and clamp all others to English."""

    snapshot = resolve_locale(
        LanguagePreference.system(),
        ui_languages=ui_languages,
    )

    assert snapshot.requested.is_system
    assert snapshot.effective_language.identifier == expected_language
    assert snapshot.formatting_locale == expected_formatting_locale


def test_explicit_preference_ignores_current_machine_language() -> None:
    """Keep a user override stable when the machine UI language differs."""

    snapshot = resolve_locale(
        LanguagePreference.explicit("ja"),
        ui_languages=("zh-CN",),
    )

    assert snapshot.requested.storage_value == "ja"
    assert snapshot.effective_language.identifier == "ja"
    assert snapshot.formatting_locale == "ja-JP"


def test_process_override_precedes_persisted_and_system_languages() -> None:
    """Use a validated handoff override without changing the saved preference."""

    snapshot = resolve_locale(
        LanguagePreference.explicit("ja"),
        ui_languages=("ja-JP",),
        process_override="zh-Hans",
    )

    assert snapshot.requested.storage_value == "ja"
    assert snapshot.effective_language.identifier == "zh-Hans"
    assert snapshot.formatting_locale == "zh-CN"


@pytest.mark.parametrize(
    ("raw_override", "expected"),
    [
        ("en-US", "en"),
        ("zh_CN", "zh-Hans"),
        ("ja-JP", "ja"),
    ],
)
def test_locale_override_accepts_only_supported_effective_languages(
    raw_override: str,
    expected: str,
) -> None:
    """Convert locale-like CLI values to stable manifest language IDs."""

    assert parse_locale_override(raw_override) == expected


@pytest.mark.parametrize("raw_override", ["system", "zh-TW", "de-DE", ""])
def test_locale_override_rejects_unsupported_or_automatic_values(
    raw_override: str,
) -> None:
    """Reject ambiguous process overrides before executable composition."""

    with pytest.raises(ValueError, match="locale override"):
        parse_locale_override(raw_override)


def test_locale_argument_uses_stable_effective_language_id() -> None:
    """Format one crash-safe launcher or splash handoff argument."""

    assert format_locale_argument("zh-Hans") == "--locale=zh-Hans"


def test_preference_store_defaults_missing_file_to_system(tmp_path: Path) -> None:
    """Use automatic language selection for a fresh installation."""

    store = LocalizationPreferenceStore.for_install_root(tmp_path)

    assert store.load() == LanguagePreference.system()


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        "[]",
        '{"schema_version": 2, "language": "ja"}',
        '{"schema_version": 1, "language": "de"}',
        '{"schema_version": 1, "language": 12}',
    ],
)
def test_preference_store_clamps_invalid_content_once(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    payload: str,
) -> None:
    """Recover corrupt or unsupported preferences with one actionable warning."""

    store = LocalizationPreferenceStore.for_install_root(tmp_path)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(payload, encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        preference = store.load()

    assert preference == LanguagePreference.system()
    assert [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(caplog.records) == 1


def test_preference_store_round_trips_stable_atomic_json(tmp_path: Path) -> None:
    """Persist the requested mode independently from its current resolution."""

    store = LocalizationPreferenceStore.for_install_root(tmp_path)

    store.save(LanguagePreference.explicit("ja"))

    assert store.load() == LanguagePreference.explicit("ja")
    assert json.loads(store.path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "language": "ja",
    }
    assert store.path.read_text(encoding="utf-8") == (
        '{\n  "schema_version": 1,\n  "language": "ja"\n}\n'
    )
    assert not store.temporary_path.exists()


def test_preference_store_failed_replace_preserves_previous_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave the last durable preference intact when atomic promotion fails."""

    store = LocalizationPreferenceStore.for_install_root(tmp_path)
    store.save(LanguagePreference.explicit("en"))

    def fail_replace(_source: Path, _destination: Path) -> None:
        """Simulate an operating-system failure during atomic promotion."""

        raise OSError("replace failed")

    monkeypatch.setattr(
        "sugarsubstitute_shared.localization.file_store.os.replace",
        fail_replace,
    )

    with pytest.raises(OSError, match="replace failed"):
        store.save(LanguagePreference.explicit("ja"))

    assert store.load() == LanguagePreference.explicit("en")
    assert not store.temporary_path.exists()
