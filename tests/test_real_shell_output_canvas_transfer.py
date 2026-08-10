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

"""Verify grid-target Output Copy through the complete offscreen shell composition."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent

from substitute.presentation.canvas.output import output_grid_context_menu
from substitute.presentation.shell import main_window_composition
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real Output CuteCanvas shell harness requires non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_grid_context_copy_materializes_the_clicked_output_mime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Copy one grid target without activating it or consulting later selection state."""

    rendered_models: list[MenuModel] = []
    published_mime_data: list[object] = []

    class _Menu:
        """Accept a production menu execution without opening a native popup."""

        def exec(self, _position: object, **_kwargs: object) -> None:
            """Preserve the renderer execution contract in the offscreen harness."""

    class _Renderer:
        """Capture the production grid menu model before it reaches Qt widgets."""

        def __init__(self, *, parent: object) -> None:
            """Accept the production renderer constructor arguments."""

            del parent

        def render(self, model: MenuModel) -> _Menu:
            """Capture one menu model instead of allocating a native popup."""

            rendered_models.append(model)
            return _Menu()

    monkeypatch.setattr(output_grid_context_menu, "QFluentMenuRenderer", _Renderer)
    monkeypatch.setattr(
        main_window_composition,
        "publish_output_transfer_mime_data",
        published_mime_data.append,
    )
    harness = RealShellOutputCanvasHarness(output_root=tmp_path)
    try:
        harness.add_workflow("alpha", activate=True)
        run = harness.start_run("alpha")
        first_path = harness.emit_output(
            run,
            OutputSpec("source", "Source", (190, 20, 40), list_index=0),
        )
        second_path = harness.emit_output(
            run,
            OutputSpec("source", "Source", (20, 190, 40), list_index=1),
        )
        harness.wait_for_output_count("alpha", 2)
        harness.shell.output_canvas.activeOutputGridChanged.emit("source")
        harness.process_events(cycles=8)

        workflow = harness.shell.workflow_session_service.workflows[
            harness.workflows["alpha"].workflow_id
        ]
        first_id, second_id = workflow.output_image_uuids
        document = harness.shell.output_canvas.document
        second_composition_id = document.composition_id_for(second_id)
        assert second_composition_id is not None
        target = harness.shell.output_canvas.workspace.canvasFor(second_composition_id)
        assert target is not None
        active_before = document.session.active_composition_id

        harness.app.sendEvent(
            target,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse,
                QPoint(4, 4),
                QPoint(24, 28),
            ),
        )

        assert len(rendered_models) == 1
        actions = tuple(
            entry for entry in rendered_models[0].entries if isinstance(entry, MenuItem)
        )
        assert tuple(action.action_id for action in actions) == (
            "output_canvas.copy",
            "output_canvas.open_current_external",
            "output_canvas.reveal_current_asset",
            "output_canvas.dock_action",
        )
        assert actions[2].enabled is True
        assert actions[0].callback is not None
        actions[0].callback()

        harness.wait_until(lambda: len(published_mime_data) == 1)
        mime_data = published_mime_data[0]
        mime_data_data = getattr(mime_data, "data")
        mime_data_urls = getattr(mime_data, "urls")
        assert bytes(mime_data_data("image/png").data()).startswith(b"\x89PNG")
        assert tuple(Path(url.toLocalFile()) for url in mime_data_urls()) == (
            second_path,
        )
        assert str(first_path) != str(second_path)
        assert document.session.active_composition_id == active_before
        assert first_id != second_id
    finally:
        harness.close()
