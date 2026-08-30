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

"""Test active generative-model candidate selection for an editor panel."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
    matching_catalog_item,
)


def test_active_model_uses_stack_order_across_checkpoint_and_diffusion_fields() -> None:
    """Select the first stack-ordered generative model as panel context."""

    context = PanelActiveModelContextController()
    context.begin_projection(("First", "Later"))
    context.record_node_inputs(
        cube_alias="Later",
        node_name="checkpoint",
        node_type="CheckpointLoaderSimple",
        inputs={"ckpt_name": "later.safetensors"},
    )
    context.record_node_inputs(
        cube_alias="First",
        node_name="models",
        node_type="SimpleSyrup.SimpleLoadAnima",
        inputs={"diffusion_model": "Anima/first.safetensors"},
    )

    candidate = context.current_model()

    assert candidate is not None
    assert candidate.model_kind == "diffusion_models"
    assert candidate.value == "Anima/first.safetensors"


def test_active_model_field_update_supports_unet_and_removal() -> None:
    """Update and remove a live diffusion-model field from active context."""

    context = PanelActiveModelContextController()
    context.begin_projection(("Base",))

    assert context.update_field_value(
        cube_alias="Base",
        node_name="model",
        node_type="UNETLoader",
        field_key="unet_name",
        value="flux.safetensors",
    )
    assert context.current_model() is not None
    assert context.update_field_value(
        cube_alias="Base",
        node_name="model",
        node_type="UNETLoader",
        field_key="unet_name",
        value="",
    )
    assert context.current_model() is None


def test_active_model_cube_rename_preserves_candidate_precedence() -> None:
    """Retain stack precedence when a cube alias changes."""

    context = PanelActiveModelContextController()
    context.begin_projection(("First", "Later"))
    context.record_node_inputs(
        cube_alias="First",
        node_name="model",
        node_type="UNETLoader",
        inputs={"unet_name": "first.safetensors"},
    )
    context.record_node_inputs(
        cube_alias="Later",
        node_name="model",
        node_type="UNETLoader",
        inputs={"unet_name": "later.safetensors"},
    )

    context.rename_cube("First", "Renamed")

    candidate = context.current_model()
    assert candidate is not None
    assert candidate.cube_alias == "Renamed"
    assert candidate.value == "first.safetensors"


def test_matching_catalog_item_supports_paths_basenames_and_stems() -> None:
    """Match backend paths, basenames, and stems against catalog items."""

    item = _model_item(
        "checkpoints",
        "models/checkpoints/illustrious.safetensors",
        "Illustrious",
    )

    assert (
        matching_catalog_item("models\\checkpoints\\illustrious.safetensors", (item,))
        is item
    )
    assert matching_catalog_item("illustrious.safetensors", (item,)) is item
    assert matching_catalog_item("illustrious", (item,)) is item


def _model_item(kind: str, backend_value: str, display_name: str) -> ModelCatalogItem:
    """Build one deterministic catalog item for matching contracts."""

    basename = backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors")
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="models",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=display_name.casefold(),
    )
