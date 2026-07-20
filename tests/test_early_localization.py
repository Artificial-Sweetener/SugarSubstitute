#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Test lightweight locale and text resolution before the parent Qt app exists."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.early_splash_text import translate_early_splash_text
from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
    resolve_early_startup_locale,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_early_locale_uses_explicit_install_root_preference(tmp_path: Path) -> None:
    """Find durable user intent before normal installation context composition."""

    install_root = tmp_path / "SugarSubstitute"
    LocalizationPreferenceStore.for_install_root(install_root).save(
        LanguagePreference.explicit("ja")
    )

    resolved = resolve_early_startup_locale(
        ["main.py", f"--install-root={install_root}"],
        app_root=tmp_path / "source",
        ui_languages=("zh-CN",),
    )

    assert resolved.requested == LanguagePreference.explicit("ja")
    assert resolved.effective_language.identifier == "ja"


def test_early_locale_infers_installed_app_payload_root(tmp_path: Path) -> None:
    """Read shared settings when a direct installed payload omits its root flag."""

    install_root = tmp_path / "SugarSubstitute"
    app_root = install_root / "app"
    app_root.mkdir(parents=True)
    (install_root / "launcher").mkdir()
    LocalizationPreferenceStore.for_install_root(install_root).save(
        LanguagePreference.explicit("zh-Hans")
    )

    resolved = resolve_early_startup_locale(
        ["main.py"],
        app_root=app_root,
        ui_languages=("en-US",),
    )

    assert resolved.effective_language.identifier == "zh-Hans"


def test_early_locale_process_handoff_precedes_saved_intent(tmp_path: Path) -> None:
    """Keep a crash-safe effective handoff separate from the stored request."""

    LocalizationPreferenceStore.for_install_root(tmp_path).save(
        LanguagePreference.explicit("ja")
    )

    resolved = resolve_early_startup_locale(
        ["main.py", "--locale=zh_CN"],
        app_root=tmp_path,
        ui_languages=("en-US",),
    )

    assert resolved.requested == LanguagePreference.explicit("ja")
    assert resolved.effective_language.identifier == "zh-Hans"


def test_early_splash_fixed_progress_uses_app_catalog_without_qapplication() -> None:
    """Translate the first IPC progress line before normal app composition."""

    assert (
        translate_early_splash_text(
            app_root=_PROJECT_ROOT,
            language_identifier="zh-Hans",
            source_text="Starting SugarSubstitute.",
        )
        == "正在启动 SugarSubstitute。"
    )
    assert (
        translate_early_splash_text(
            app_root=_PROJECT_ROOT,
            language_identifier="ja",
            source_text="Starting SugarSubstitute.",
        )
        == "SugarSubstitute を起動しています。"
    )
