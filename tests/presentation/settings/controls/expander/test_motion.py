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

"""Test deterministic Settings expander motion contracts."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.presentation.settings.settings_expander import (
    SettingsExpander,
)
from tests.presentation.settings.controls.expander.support import (
    application,
    motion_animations,
    wait_for_motion,
)


def test_settings_expander_uses_node_card_style_motion(
    owned_widgets: list[QWidget],
) -> None:
    """Expansion and collapse should slide clipped body content like node cards."""

    app = application()
    expander = SettingsExpander(title="Tracked pack", expanded=True)
    owned_widgets.append(expander)
    child = QWidget(expander.content_widget())
    child.setFixedHeight(140)
    expander.add_widget(child)
    expander.show()
    app.processEvents()

    expanded_height = expander.content_widget().sizeHint().height()

    expander.set_expanded(False)
    for animation in motion_animations(expander):
        animation.setCurrentTime(min(40, animation.duration() - 1))

    assert expander.content_clip_visible() is True
    assert -expanded_height < expander.content_offset_y() < 0
    assert expander.header_separator_visible() is False

    wait_for_motion(expander)

    assert expander.content_clip_visible() is False
    assert expander.content_offset_y() == -expanded_height
    assert expander.chevron.rotation_value() == 0.0

    expander.set_expanded(True)
    wait_for_motion(expander)

    assert expander.content_clip_visible() is True
    assert expander.content_offset_y() == 0
    assert expander.header_separator_visible() is True
    assert expander.chevron.rotation_value() == 180.0
