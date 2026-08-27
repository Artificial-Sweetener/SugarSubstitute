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

"""Provide shared generation titlebar test values and Qt access."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
    GenerationPlayPresentationMode,
)
from tests.support.qt.lifecycle import ensure_qt_application


def app() -> QApplication:
    """Return the worker-local Qt application held by the package fixture."""

    return ensure_qt_application()


def presentation(
    *,
    play_mode: GenerationPlayPresentationMode = "generate",
    play_enabled: bool = True,
    play_tooltip: str = "Generate",
    stop_enabled: bool = False,
    skip_enabled: bool = False,
    queue_primary_enabled: bool = False,
    queue_badge_count: int = 0,
    queue_segment_visible: bool = True,
    batch_accessory_visible: bool = True,
    batch_accessory_enabled: bool = True,
    mode_menu_enabled: bool = True,
) -> GenerationActionPresentation:
    """Return one titlebar generation presentation for widget contracts."""

    return GenerationActionPresentation(
        play_mode=play_mode,
        play_enabled=play_enabled,
        play_tooltip=play_tooltip,
        stop_enabled=stop_enabled,
        skip_enabled=skip_enabled,
        queue_primary_enabled=queue_primary_enabled,
        queue_badge_count=queue_badge_count,
        queue_segment_visible=queue_segment_visible,
        batch_accessory_visible=batch_accessory_visible,
        batch_accessory_enabled=batch_accessory_enabled,
        mode_menu_enabled=mode_menu_enabled,
    )


__all__ = ["app", "presentation"]
