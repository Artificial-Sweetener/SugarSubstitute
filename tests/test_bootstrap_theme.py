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

"""Tests for shared QFluent theme bootstrap behavior."""

from __future__ import annotations

import sys
import types

from PySide6.QtGui import QColor
import pytest

from substitute.app.bootstrap import theme
from substitute.domain.appearance import AppearanceThemeMode


def test_configure_theme_applies_requested_theme_and_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared theme setup should drive QFluent theme and accent APIs."""

    calls: list[tuple[str, object]] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(
        qfluentwidgets,
        "setTheme",
        lambda value: calls.append(("theme", value)),
    )
    setattr(
        qfluentwidgets,
        "setThemeColor",
        lambda value: calls.append(("accent", value)),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)

    theme.configure_theme(
        theme_mode=AppearanceThemeMode.LIGHT,
        accent_color="#123456",
    )

    assert calls == [
        ("theme", "light"),
        ("accent", QColor("#123456")),
    ]


def test_configure_theme_rejects_unresolved_auto_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Require runtime system detection to resolve Auto before QFluent setup."""

    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets,
        "Theme",
        types.SimpleNamespace(LIGHT="light", DARK="dark", AUTO="auto"),
    )
    setattr(qfluentwidgets, "setTheme", lambda _value: None)
    setattr(qfluentwidgets, "setThemeColor", lambda _value: None)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)

    with pytest.raises(ValueError, match="Auto theme must be resolved"):
        theme.configure_theme(
            theme_mode=AppearanceThemeMode.AUTO,
            accent_color="#123456",
        )


def test_configure_accent_color_applies_only_requested_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accent-only setup should avoid mutating the QFluent theme mode."""

    calls: list[tuple[str, object]] = []
    qfluentwidgets = types.ModuleType("qfluentwidgets")
    setattr(
        qfluentwidgets, "setThemeColor", lambda value: calls.append(("accent", value))
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfluentwidgets)

    theme.configure_accent_color(accent_color="#654321")

    assert calls == [("accent", QColor("#654321"))]
