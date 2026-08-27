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

"""Test recipe output sibling restoration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append_then,
    _EditorBusyRecorder,
    _noop_output_registrar,
    _recipe_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_load_recipe_document_restores_discovered_png_output_siblings(
    tmp_path: Path,
) -> None:
    """Loading a recipe PNG should restore discovered same-folder output siblings."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "881_untitled_recipe_text_to_image.png"
    sibling_path = tmp_path / "881_untitled_recipe_diffusion_upscale.png"
    metadata_calls: list[dict[str, object]] = []
    added_outputs: list[tuple[str, object, object]] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }
    discovery_result = mod.RecipeOutputSiblingDiscoveryResult(
        siblings=(
            mod.RecipeOutputSibling(
                path=source_path,
                source_key="text_to_image",
                source_label="Text to Image",
                sequence=1,
                node_title="Text",
            ),
            mod.RecipeOutputSibling(
                path=sibling_path,
                source_key="diffusion_upscale",
                source_label="Diffusion Upscale",
                sequence=2,
                node_title="Upscale",
            ),
        ),
        strategy="same_folder_pattern",
    )
    discovery_calls: list[tuple[Path, str]] = []

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: f"image:{path.name}",
            build_output_image_metadata=lambda **kwargs: _append_then(
                metadata_calls,
                kwargs,
                f"meta:{kwargs['source_key']}",
            ),
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=lambda path, *, workflow_name: _append_then(
                discovery_calls,
                (path, workflow_name),
                discovery_result,
            )
        ),
    )

    actions.load_recipe_document(
        source_path,
        projects_dir=tmp_path,
        cube_loader=lambda *_args, **_kwargs: None,
    )

    assert discovery_calls == [(source_path, "Untitled Workflow")]
    assert [call["file_path"] for call in metadata_calls] == [source_path, sibling_path]
    assert [call["workflow_name"] for call in metadata_calls] == [
        "Untitled Workflow",
        "Untitled Workflow",
    ]
    assert [call["source_key"] for call in metadata_calls] == [
        "text_to_image",
        "diffusion_upscale",
    ]
    assert added_outputs == [
        (
            workflow_id,
            "image:881_untitled_recipe_text_to_image.png",
            "meta:text_to_image",
        ),
        (
            workflow_id,
            "image:881_untitled_recipe_diffusion_upscale.png",
            "meta:diffusion_upscale",
        ),
    ]


def test_load_recipe_document_skips_unreadable_discovered_png_sibling(
    tmp_path: Path,
) -> None:
    """Unreadable sibling images should not block the recipe load."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    source_path = tmp_path / "881_untitled_recipe_text_to_image.png"
    broken_path = tmp_path / "881_untitled_recipe_broken.png"
    added_outputs: list[tuple[str, object, object]] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }
    discovery_result = mod.RecipeOutputSiblingDiscoveryResult(
        siblings=(
            mod.RecipeOutputSibling(
                path=source_path,
                source_key="text_to_image",
                source_label="Text to Image",
                sequence=1,
            ),
            mod.RecipeOutputSibling(
                path=broken_path,
                source_key="broken",
                source_label="Broken",
                sequence=2,
            ),
        ),
        strategy="same_folder_pattern",
    )

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: _CubeStack()},
        editor_panels={workflow_id: _EditorPanel()},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: (
                None if path == broken_path else f"image:{path.name}"
            ),
            build_output_image_metadata=lambda **kwargs: f"meta:{kwargs['source_key']}",
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=lambda *_args, **_kwargs: discovery_result
        ),
    )

    result = actions.load_recipe_document(
        source_path,
        projects_dir=tmp_path,
        cube_loader=lambda *_args, **_kwargs: None,
    )

    assert result == workflow_id
    assert added_outputs == [
        (
            workflow_id,
            "image:881_untitled_recipe_text_to_image.png",
            "meta:text_to_image",
        )
    ]


def test_load_recipe_document_does_not_discover_siblings_for_text_recipe(
    tmp_path: Path,
) -> None:
    """Text recipe loads should not invoke PNG output sibling discovery."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    source_path = tmp_path / "recipe.sugar"
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    def _unexpected_discovery(*_args: object, **_kwargs: object) -> object:
        """Fail if text recipes attempt PNG sibling discovery."""

        raise AssertionError("text recipe should not discover image siblings")

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: _CubeStack()},
        editor_panels={workflow_id: _EditorPanel()},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=_unexpected_discovery
        ),
    )

    assert (
        actions.load_recipe_document(
            source_path,
            projects_dir=tmp_path,
            cube_loader=lambda *_args, **_kwargs: None,
        )
        == workflow_id
    )
