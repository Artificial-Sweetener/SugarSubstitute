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

"""Test workspace document open routing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append_then,
    _noop_output_registrar,
)


def test_open_routes_dual_metadata_png_only_to_sugar_recipe() -> None:
    """The first-party SugarScript path should take precedence over direct Comfy."""

    mod = _import_module()
    source = Path("E:/workflows/dual-metadata.png")
    recipe_paths: list[Path] = []
    direct_paths: list[Path] = []
    view = SimpleNamespace(
        recipe_io_service=SimpleNamespace(
            classify_recipe_document=lambda _path: SimpleNamespace(supported=True)
        ),
        path_bundle=SimpleNamespace(
            projects_dir=Path("E:/projects"),
            sugar_scripts_dir=Path("E:/projects"),
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: None,
        output_image_registrar=_noop_output_registrar(),
    )
    setattr(
        actions,
        "load_recipe_document",
        lambda path, **_kwargs: _append_then(recipe_paths, path, "recipe"),
    )
    dialog = SimpleNamespace(
        getOpenFileName=lambda *_args, **_kwargs: (str(source), "Workflows")
    )

    actions.on_load_clicked(
        file_dialog=dialog,
        load_direct_workflow_document=lambda path: _append_then(
            direct_paths, path, "direct"
        ),
        can_load_direct_workflow_document=lambda _path: True,
    )

    assert recipe_paths == [source]
    assert direct_paths == []


def test_open_routes_workflow_only_png_to_direct_comfy_loader() -> None:
    """A PNG without SugarScript metadata should fall back to direct Comfy loading."""

    mod = _import_module()
    source = Path("E:/workflows/comfy-only.png")
    recipe_paths: list[Path] = []
    direct_paths: list[Path] = []
    view = SimpleNamespace(
        recipe_io_service=SimpleNamespace(
            classify_recipe_document=lambda _path: SimpleNamespace(supported=False)
        ),
        path_bundle=SimpleNamespace(
            projects_dir=Path("E:/projects"),
            sugar_scripts_dir=Path("E:/projects"),
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: None,
        output_image_registrar=_noop_output_registrar(),
    )
    setattr(
        actions,
        "load_recipe_document",
        lambda path, **_kwargs: _append_then(recipe_paths, path, "recipe"),
    )
    dialog = SimpleNamespace(
        getOpenFileName=lambda *_args, **_kwargs: (str(source), "Workflows")
    )

    actions.on_load_clicked(
        file_dialog=dialog,
        load_direct_workflow_document=lambda path: _append_then(
            direct_paths, path, "direct"
        ),
        can_load_direct_workflow_document=lambda _path: True,
    )

    assert recipe_paths == []
    assert direct_paths == [source]
