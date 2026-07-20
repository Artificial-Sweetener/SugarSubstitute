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

"""Test locale-aware font synchronization at QFluent's independent owner."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]
from qfluentwidgets.common.font import (  # type: ignore[import-untyped]
    fontFamilies,
    getFont,
)

from sugarsubstitute_shared.presentation.localization import (
    QFluentFontFamilyAdapter,
)
from substitute.presentation.workflows.cube_stack_view import CubeStack


def test_adapter_updates_existing_and_future_qfluent_fonts() -> None:
    """Use Japanese fallbacks for both mounted labels and future QFluent fonts."""

    application = cast(
        QApplication,
        QApplication.instance() or QApplication([]),
    )
    adapter = QFluentFontFamilyAdapter(application)
    initial_state = adapter.snapshot()
    label = CaptionLabel("Kサンプラー")
    localized_font = QFont(application.font())
    localized_font.setFamilies(["Segoe UI", "Yu Gothic UI", "Noto Sans CJK JP"])
    try:
        adapter.apply_application_font(localized_font)

        expected_prefix = ("Segoe UI", "Yu Gothic UI", "Noto Sans CJK JP")
        assert tuple(fontFamilies())[:3] == expected_prefix
        assert tuple(getFont(14).families())[:3] == expected_prefix
        assert tuple(label.font().families())[:3] == expected_prefix
    finally:
        adapter.restore(initial_state)
        label.deleteLater()
        application.processEvents()


def test_adapter_switches_locale_profile_without_accumulating_old_fallbacks() -> None:
    """Replace Japanese fallbacks with Chinese ones from the stable baseline."""

    application = cast(
        QApplication,
        QApplication.instance() or QApplication([]),
    )
    adapter = QFluentFontFamilyAdapter(application)
    initial_state = adapter.snapshot()
    japanese_font = QFont(application.font())
    japanese_font.setFamilies(["Segoe UI", "Yu Gothic UI"])
    chinese_font = QFont(application.font())
    chinese_font.setFamilies(["Segoe UI", "Microsoft YaHei UI"])
    try:
        adapter.apply_application_font(japanese_font)
        adapter.apply_application_font(chinese_font)

        active_families = tuple(fontFamilies())
        assert active_families[:2] == ("Segoe UI", "Microsoft YaHei UI")
        assert "Yu Gothic UI" not in active_families
    finally:
        adapter.restore(initial_state)


def test_adapter_preserves_cube_stack_transparency_styles() -> None:
    """QFluent font refreshes must not replace cube-stack transparency ownership."""

    application = cast(
        QApplication,
        QApplication.instance() or QApplication([]),
    )
    adapter = QFluentFontFamilyAdapter(application)
    initial_state = adapter.snapshot()
    stack = CubeStack()
    initial_stack_style = stack.styleSheet()
    initial_view_style = stack.view.styleSheet()
    localized_font = QFont(application.font())
    localized_font.setFamilies(["SugarSubstitute Locale Test", *fontFamilies()])
    try:
        adapter.apply_application_font(localized_font)

        assert stack.styleSheet() == initial_stack_style
        assert stack.view.styleSheet() == initial_view_style
    finally:
        adapter.restore(initial_state)
        stack.deleteLater()
        application.processEvents()
