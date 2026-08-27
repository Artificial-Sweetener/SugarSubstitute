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

"""Test workspace side-panel host geometry state."""

from __future__ import annotations

from substitute.presentation.shell.main_window_workspace import WorkspaceSidePanelHost
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_side_panel_host_keeps_durable_width_separate_from_rendered_width() -> None:
    """Animated frame width should not replace the durable side-panel width."""

    application = ensure_qt_application()
    host = WorkspaceSidePanelHost()

    try:
        assert host.is_queue_panel_visible() is False
        assert host.panel_width() == 360

        host.set_panel_width(100)

        assert host.panel_width() == 240

        host.begin_width_transition(target_visible=True)
        host.apply_width_transition(0)

        assert host.is_queue_panel_visible() is True
        assert host.rendered_width() == 0
        assert host.panel_width() == 240

        host.finish_width_transition(visible=True)

        assert host.is_queue_panel_visible() is True
        assert host.rendered_width() == 240
        assert host.panel_width() == 240

        host.begin_width_transition(target_visible=False)
        host.apply_width_transition(12)

        assert host.is_queue_panel_visible() is True
        assert host.rendered_width() == 12
        assert host.panel_width() == 240

        host.finish_width_transition(visible=False)

        assert host.is_queue_panel_visible() is False
        assert host.rendered_width() == 0
        assert host.panel_width() == 240
    finally:
        host.close()
        destroy_qt_object(host)

    assert application is ensure_qt_application()
