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

"""Build locale-specific system font fallback lists without bundled font memory."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtGui import QFont

_PROFILE_FAMILIES: Mapping[str, tuple[str, ...]] = {
    "system": (),
    "cjk-sc": (
        "Microsoft YaHei UI",
        "PingFang SC",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
    ),
    "cjk-jp": (
        "Yu Gothic UI",
        "Hiragino Sans",
        "Noto Sans CJK JP",
        "Source Han Sans JP",
    ),
    "cjk-kr": (
        "Malgun Gothic",
        "Apple SD Gothic Neo",
        "Noto Sans CJK KR",
        "Source Han Sans K",
    ),
}


def localized_application_font(base_font: QFont, profile: str) -> QFont:
    """Return a copy with deterministic CJK fallback families."""

    if profile not in _PROFILE_FAMILIES:
        raise ValueError(f"Unsupported localization font profile: {profile!r}")
    localized = QFont(base_font)
    base_families = tuple(base_font.families()) or (base_font.family(),)
    profile_families = _PROFILE_FAMILIES[profile]
    localized.setFamilies(
        list(
            dict.fromkeys(
                family for family in (*profile_families, *base_families) if family
            )
        )
    )
    return localized


__all__ = ["localized_application_font"]
