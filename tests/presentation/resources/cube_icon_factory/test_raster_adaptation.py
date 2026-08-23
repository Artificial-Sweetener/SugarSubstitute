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
    _png_bytes,
    _rgb_at,
)


def test_bright_grayscale_png_inverts_in_light_mode_preserving_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bright grayscale PNG assets should become dark in light mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(255, 255, 255, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    black = _rgb_at(image, 0, 0)
    dark_gray = _rgb_at(image, 1, 0)
    assert max(black) <= 5
    assert 45 <= dark_gray[0] <= 60
    assert black != dark_gray


def test_bright_grayscale_png_is_preserved_in_dark_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Bright grayscale PNG assets should remain bright in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(255, 255, 255, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    white = _rgb_at(image, 0, 0)
    light_gray = _rgb_at(image, 1, 0)
    assert min(white) >= 250
    assert 198 <= light_gray[0] <= 210


def test_dark_grayscale_png_inverts_in_dark_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    """Dark grayscale PNG assets should become light in dark mode."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: True)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(0, 0, 0, 255), (51, 51, 51, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    white = _rgb_at(image, 0, 0)
    light_gray = _rgb_at(image, 1, 0)
    assert min(white) >= 250
    assert 198 <= light_gray[0] <= 210


def test_full_color_png_auto_asset_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Automatic color behavior should not transform confidently colored PNGs."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(220, 24, 40, 255), (20, 120, 220, 255)]]),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    assert _rgb_at(image, 0, 0) == (220, 24, 40)
    assert _rgb_at(image, 1, 0) == (20, 120, 220)


def test_full_color_png_declared_full_color_is_left_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    """Full-color color behavior should never transform PNG assets."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes([[(250, 250, 250, 255), (204, 204, 204, 255)]]),
        media_type="image/png",
        color_behavior="fullColor",
        render_size=2,
    )

    image = _icon_image(icon, 2, 1)
    assert _rgb_at(image, 0, 0) == (250, 250, 250)
    assert _rgb_at(image, 1, 0) == (204, 204, 204)


def test_png_resize_before_adjust_preserves_gray_details(
    monkeypatch: MonkeyPatch,
) -> None:
    """Target-size PNG adjustment should invert neutral detail after scaling."""

    _ensure_qapp()
    import substitute.presentation.resources.cube_icon_factory as icon_module

    monkeypatch.setattr(icon_module, "isDarkTheme", lambda: False)
    rows = [
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
        [
            (255, 255, 255, 255),
            (255, 255, 255, 255),
            (204, 204, 204, 255),
            (204, 204, 204, 255),
        ],
    ]

    icon, _fetcher = _icon_for_asset(
        content=_png_bytes(rows),
        media_type="image/png",
        render_size=2,
    )

    image = _icon_image(icon, 2)
    assert max(_rgb_at(image, 0, 0)) <= 5
    dark_gray = _rgb_at(image, 1, 0)
    assert 45 <= dark_gray[0] <= 60
