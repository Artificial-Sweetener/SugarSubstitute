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

"""Verify shared installer-surface assets against the production Qt renderer."""

from __future__ import annotations

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtSvg import QSvgRenderer

from sugarsubstitute_shared.presentation.installer_surface import (
    installer_wordmark_path,
)


def test_installer_wordmark_uses_only_supported_qt_svg_filters() -> None:
    """Keep the production wordmark valid and free of Qt SVG parser warnings."""

    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _kind, _context, message: messages.append(message)
    )
    try:
        renderer = QSvgRenderer(str(installer_wordmark_path()))
    finally:
        qInstallMessageHandler(previous_handler)

    assert renderer.isValid()
    assert not any(message.startswith("qt.svg:") for message in messages)
