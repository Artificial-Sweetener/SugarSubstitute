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

"""Verify Qt-free operating-system UI-language discovery."""

from __future__ import annotations

import locale
import pytest

from sugarsubstitute_shared.localization import system_languages


def test_system_ui_languages_preserve_platform_precedence_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash localization should receive stable, ordered locale candidates."""

    monkeypatch.setenv("LANGUAGE", "ja:es_ES:JA")
    monkeypatch.setenv("LC_ALL", "ko_KR.UTF-8")
    monkeypatch.setenv("LC_MESSAGES", "es_ES")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setattr(
        system_languages,
        "_windows_ui_language_candidates",
        lambda: ("zh-CN", "ja"),
    )
    monkeypatch.setattr(locale, "getlocale", lambda: ("en_US", "UTF-8"))

    assert system_languages.system_ui_languages() == (
        "ja",
        "es_ES",
        "ko_KR.UTF-8",
        "en_US.UTF-8",
        "zh-CN",
        "en_US",
    )


def test_system_ui_languages_tolerate_unconfigured_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty machine locale should leave resolver fallback authoritative."""

    for variable_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(variable_name, raising=False)
    monkeypatch.setattr(
        system_languages,
        "_windows_ui_language_candidates",
        lambda: (),
    )
    monkeypatch.setattr(locale, "getlocale", lambda: (None, None))

    assert system_languages.system_ui_languages() == ()


@pytest.mark.platforms("windows")
def test_windows_ui_language_candidates_are_available() -> None:
    """Windows startup should resolve at least one kernel-owned UI language."""

    assert system_languages._windows_ui_language_candidates()
