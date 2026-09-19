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

"""Own native installer backdrop and frameless-window integration."""

from __future__ import annotations

import logging
from typing import Any

from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]


_LOGGER = logging.getLogger(__name__)


def apply_launcher_window_effects(window: Any) -> None:
    """Apply Mica Alt exactly as the main Substitute frame does."""

    try:
        window.setAutoFillBackground(False)
        window.windowEffect.setMicaEffect(
            window.winId(),
            isDarkMode=isDarkTheme(),
            isAlt=True,
        )
    except (AttributeError, RuntimeError, OSError) as error:
        _LOGGER.warning("Failed to apply launcher backdrop: %r", error)
