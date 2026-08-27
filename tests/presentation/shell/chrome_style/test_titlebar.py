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

"""Verify shell titlebar button theming."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.presentation.shell import window_frame
from tests.presentation.shell.chrome_style.support import TitleBar


@pytest.mark.parametrize("dark_theme", [False, True])
def test_shell_titlebar_button_theme_preserves_qfluent_defaults(
    monkeypatch: pytest.MonkeyPatch,
    dark_theme: bool,
) -> None:
    """Apply the QFluent stylesheet without overriding button colors."""
    monkeypatch.setattr(window_frame, "isDarkTheme", lambda: dark_theme)
    applied: list[object] = []
    monkeypatch.setattr(
        window_frame,
        "FluentStyleSheet",
        SimpleNamespace(FLUENT_WINDOW=SimpleNamespace(apply=applied.append)),
    )
    titlebar = TitleBar()

    window_frame.apply_shell_titlebar_button_theme(titlebar)

    assert applied == [titlebar.minBtn, titlebar.maxBtn, titlebar.closeBtn]
    assert titlebar.minBtn.normal_color is None
    assert titlebar.minBtn.hover_color is None
    assert titlebar.minBtn.pressed_color is None
    assert titlebar.minBtn.hover_background_color is None
    assert titlebar.minBtn.pressed_background_color is None
    assert titlebar.maxBtn.normal_color is None
    assert titlebar.closeBtn.normal_color is None
    assert titlebar.closeBtn.hover_color is None
    assert titlebar.closeBtn.hover_background_color is None
