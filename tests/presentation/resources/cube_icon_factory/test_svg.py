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

"""Contract tests for Cube Library presentation icon resolution."""

from __future__ import annotations


from pytest import MonkeyPatch
from tests.presentation.resources.cube_icon_factory.support import (
    _ensure_qapp,
    _icon_for_asset,
    _icon_image,
    _rgb_at,
)


def test_white_gray_svg_template_inverts_in_light_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Template SVG assets should preserve gray detail when inverted."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 1">'
        b'<rect width="1" height="1" fill="#ffffff"/>'
        b'<rect x="1" width="1" height="1" fill="#cccccc"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        color_behavior="template",
        render_size=20,
    )

    image = _icon_image(icon, 20, 20)
    black = _rgb_at(image, 5, 10)
    dark_gray = _rgb_at(image, 15, 10)
    assert max(black) <= 5
    assert 45 <= dark_gray[0] <= 60


def test_colored_svg_auto_asset_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Automatic color behavior should not transform colored SVG assets."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
        b'<rect width="1" height="1" fill="#dc1828"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        render_size=20,
    )

    red = _rgb_at(_icon_image(icon, 20, 20), 10, 10)
    assert red[0] >= 210
    assert red[1] <= 35
    assert red[2] <= 50


def test_current_color_svg_template_uses_theme_foreground(
    monkeypatch: MonkeyPatch,
) -> None:
    """Template SVG currentColor declarations should use the theme foreground."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
        b'<rect width="1" height="1" fill="currentColor"/>'
        b"</svg>"
    )

    icon, _fetcher = _icon_for_asset(
        content=svg,
        media_type="image/svg+xml",
        color_behavior="template",
        render_size=20,
    )

    foreground = _rgb_at(_icon_image(icon, 20, 20), 10, 10)
    assert 25 <= foreground[0] <= 40
    assert 25 <= foreground[1] <= 40
    assert 25 <= foreground[2] <= 40
