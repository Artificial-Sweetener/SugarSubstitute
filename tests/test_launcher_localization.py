#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Test installer locale resolution, translator composition, and headless seeding."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
    resolve_launcher_locale,
    seed_headless_locale_preference,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.localization import (
    LanguagePreference,
    LocalizationPreferenceStore,
)


def test_launcher_resolution_honors_persisted_preference_and_process_override(
    tmp_path: Path,
) -> None:
    """Keep durable user intent separate from one effective handoff override."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    store = LocalizationPreferenceStore.for_install_root(layout.root)
    store.save(LanguagePreference.explicit("zh-Hans"))

    persisted = resolve_launcher_locale(layout, locale_override=None)
    overridden = resolve_launcher_locale(layout, locale_override="ja")

    assert persisted.requested == LanguagePreference.explicit("zh-Hans")
    assert persisted.effective_language.identifier == "zh-Hans"
    assert overridden.requested == LanguagePreference.explicit("zh-Hans")
    assert overridden.effective_language.identifier == "ja"


def test_launcher_runtime_installs_japanese_before_window_construction(
    tmp_path: Path,
) -> None:
    """Translate launcher and Fluent controls before the main window is imported."""

    application = _application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    runtime = build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override="ja",
    )

    assert runtime.initial_snapshot.effective_language_identifier == "ja"
    assert (
        QCoreApplication.translate("LauncherMainWindow", "SugarSubstitute Setup")
        == "SugarSubstitute セットアップ"
    )
    assert QCoreApplication.translate("SwitchButton", "On") == "オン"
    runtime.manager.close()


def test_launcher_uses_startup_locale_without_exposing_a_language_selector(
    tmp_path: Path,
) -> None:
    """Keep installer locale automatic and omit user-selectable installer UI."""

    application = _application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    runtime = build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override="zh-Hans",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
    )

    try:
        assert window.windowTitle() == "SugarSubstitute 安装程序"
        assert window.progress_title_label.text() == "选择文件夹"
        assert window.findChild(QWidget, "LauncherLanguageSelector") is None
    finally:
        window.close()
        runtime.manager.close()


def test_headless_locale_override_seeds_shared_durable_preference(
    tmp_path: Path,
) -> None:
    """Persist headless language selection for later launcher and app starts."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    seed_headless_locale_preference(layout, locale_override="zh-Hans")

    assert LocalizationPreferenceStore.for_install_root(layout.root).load() == (
        LanguagePreference.explicit("zh-Hans")
    )


def _application() -> QApplication:
    """Return the process application used by launcher translation composition."""

    return cast(QApplication, QApplication.instance() or QApplication([]))
