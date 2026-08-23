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

"""Verify prompt projection surface paint reads only published render state."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
)


def test_paint_reads_only_event_clip_and_published_render_frame(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject mutable-state discovery from the paint path."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="alpha beta", width=360)
    surface = surface_for(box)
    process_events(app)

    def reject_discovery(*args: object, **kwargs: object) -> None:
        """Reject render-frame preparation reached from paint."""

        del args, kwargs
        raise AssertionError("paint discovered mutable prompt state")

    for method_name in (
        "_publish_render_frame",
        "_should_paint_caret",
        "_preview_visible_region",
        "_fresh_reorder_surface_chrome",
    ):
        monkeypatch.setattr(surface, method_name, reject_discovery)

    image = render_surface_viewport(surface)

    assert not image.isNull()
