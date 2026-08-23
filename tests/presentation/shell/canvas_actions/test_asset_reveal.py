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

"""Test workspace output asset reveal actions."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.ports.file_manager_gateway import (
    FileRevealResult,
    FileRevealStatus,
)


from tests.presentation.shell.canvas_actions.support import (
    _import_module,
    _record_and_return,
)


def test_reveal_output_asset_delegates_metadata_path_to_application_service() -> None:
    """Output-context intent should remain a thin adapter over the reveal use case."""

    mod = _import_module()
    paths: list[str] = []
    reveal_service = SimpleNamespace(
        reveal_asset=lambda path: _record_and_return(
            paths,
            path,
            FileRevealResult(FileRevealStatus.REVEALED),
        )
    )
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        asset_reveal_service=reveal_service,
    )

    revealed = actions.reveal_output_asset(SimpleNamespace(path="C:/outputs/image.png"))

    assert revealed is True
    assert paths == ["C:/outputs/image.png"]


def test_reveal_output_asset_rejects_metadata_without_path() -> None:
    """Malformed metadata should not invoke the application reveal service."""

    mod = _import_module()
    reveal_service = SimpleNamespace(
        reveal_asset=lambda _path: (_ for _ in ()).throw(
            AssertionError("missing paths must not be revealed")
        )
    )
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        asset_reveal_service=reveal_service,
    )

    assert actions.reveal_output_asset(SimpleNamespace(path=None)) is False


def test_workspace_canvas_actions_no_longer_owns_input_phase16_policy() -> None:
    """Input mask tools, presenter intent, and picker refresh live outside actions."""

    mod = _import_module()
    action_names = set(dir(mod.WorkspaceCanvasActions))
    retired_names = {
        "on_input_image_changed",
        "on_input_canvas_image_loaded",
        "reconcile_active_input_canvas_image",
        "on_input_image_clicked",
        "refresh_active_mask_pickers",
        "on_input_mask_changed",
        "on_input_mask_clicked",
        "on_mask_save_completed",
        "materialize_loaded_cube_input_canvas",
    }

    assert action_names.isdisjoint(retired_names)
