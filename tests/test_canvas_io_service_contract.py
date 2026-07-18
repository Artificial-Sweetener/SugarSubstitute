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

"""Contract tests for CanvasIoService path and metadata orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.workflows import CanvasIoService
from substitute.domain.workflow import ImageMeta


def _repo(**overrides: object) -> SimpleNamespace:
    """Build a small image repository test double."""

    defaults = {
        "load_image": lambda _path: None,
        "save_blank_mask": lambda *_a, **_k: True,
        "save_blank_image": lambda *_a, **_k: True,
        "save_image": lambda *_a, **_k: True,
        "image_dimensions": lambda _path: None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_expected_bound_mask_path_names_mask_for_input_image(tmp_path: Path) -> None:
    """Bound mask paths should be deterministic and named for the input image."""

    service = CanvasIoService(image_repository=_repo())

    path = service.expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("C:/images/cat portrait.png"),
        cube_alias="Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(1024, 768),
        projects_dir=tmp_path,
    )

    assert path.parent == (tmp_path / "Recipe" / "masks").resolve()
    assert path.name.startswith("cat_portrait__")
    assert "__1024x768__Inpaint__load_image_as_mask.png" in path.name


def test_expected_bound_mask_path_hashes_equal_stems_from_different_folders(
    tmp_path: Path,
) -> None:
    """Bound mask paths should not collide for equal input stems in different dirs."""

    service = CanvasIoService(image_repository=_repo())

    first = service.expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("C:/photos/cat.png"),
        cube_alias="Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(512, 512),
        projects_dir=tmp_path,
    )
    second = service.expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("D:/references/cat.png"),
        cube_alias="Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(512, 512),
        projects_dir=tmp_path,
    )

    assert first.name != second.name
    assert first.name.startswith("cat__")
    assert second.name.startswith("cat__")


def test_expected_bound_mask_path_encodes_slash_bearing_cube_alias(
    tmp_path: Path,
) -> None:
    """Model-prefixed cube aliases should remain valid generated mask filenames."""

    service = CanvasIoService(image_repository=_repo())

    path = service.expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("C:/images/cat.png"),
        cube_alias="SDXL/Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(512, 512),
        projects_dir=tmp_path,
    )

    assert path.parent == (tmp_path / "Recipe" / "masks").resolve()
    assert "SDXL_Inpaint" in path.name
    assert "/" not in path.name
    assert "\\" not in path.name
    assert path.suffix == ".png"


def test_allocate_bound_mask_path_adds_variant_when_preferred_exists(
    tmp_path: Path,
) -> None:
    """Bound mask allocation should preserve an incompatible preferred artifact."""

    service = CanvasIoService(image_repository=_repo())
    preferred = service.expected_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("C:/images/cat.png"),
        cube_alias="Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(512, 512),
        projects_dir=tmp_path,
    )
    preferred.parent.mkdir(parents=True, exist_ok=True)
    preferred.write_bytes(b"old mask")

    allocated = service.allocate_bound_mask_path(
        workflow_name="Recipe",
        associated_image_path=Path("C:/images/cat.png"),
        cube_alias="Inpaint",
        mask_node_name="load_image_as_mask",
        image_size=(512, 512),
        projects_dir=tmp_path,
    )

    assert allocated == preferred.with_name(f"{preferred.stem}__v02.png")


def test_image_dimensions_delegates_to_image_repository(tmp_path: Path) -> None:
    """Canvas IO should expose image dimensions through its repository boundary."""

    calls: list[Path] = []

    def _image_dimensions(path: Path) -> tuple[int, int]:
        calls.append(path)
        return (320, 240)

    service = CanvasIoService(
        image_repository=_repo(image_dimensions=_image_dimensions)
    )
    path = tmp_path / "image.png"

    dimensions = service.image_dimensions(path)

    assert dimensions == (320, 240)
    assert calls == [path]


def test_synthetic_input_surface_path_is_deterministic_and_project_scoped(
    tmp_path: Path,
) -> None:
    """Synthetic surfaces should have stable safe paths under workflow ownership."""

    service = CanvasIoService(image_repository=_repo())

    first = service.synthetic_input_surface_path(
        workflow_name="Regional",
        section_key="SDXL/Regions",
        surface_key="@synthetic/authority",
        width=1024,
        height=768,
        projects_dir=tmp_path,
    )
    second = service.synthetic_input_surface_path(
        workflow_name="Regional",
        section_key="SDXL/Regions",
        surface_key="@synthetic/authority",
        width=1024,
        height=768,
        projects_dir=tmp_path,
    )

    assert first == second
    assert first.parent == (tmp_path / "Regional" / "input_surfaces").resolve()
    assert "1024x768" in first.name
    assert "/" not in first.name
    assert "\\" not in first.name


def test_resolve_mask_path_handles_relative_and_absolute_paths(tmp_path: Path) -> None:
    """Mask path resolution should preserve absolute paths and expand relative paths."""

    service = CanvasIoService(image_repository=_repo())
    relative = service.resolve_mask_path(
        workflow_name="Recipe",
        path_from_buffer="mask_a.png",
        projects_dir=tmp_path,
    )
    absolute_input = (tmp_path / "absolute.png").resolve()
    absolute = service.resolve_mask_path(
        workflow_name="Recipe",
        path_from_buffer=str(absolute_input),
        projects_dir=tmp_path,
    )

    assert relative == (tmp_path / "Recipe" / "masks" / "mask_a.png").resolve()
    assert absolute == absolute_input


def test_build_output_image_metadata_parses_number_cube_alias_and_suffix() -> None:
    """Metadata builder should parse prefixed number, cube alias, and suffix text."""

    service = CanvasIoService(image_repository=_repo())

    metadata = service.build_output_image_metadata(
        workflow_name="Recipe",
        node_meta_title="CubeX.KSampler",
        file_path=Path("E:/projects/007_preview_out.png"),
    )

    assert metadata.workflow_name == "Recipe"
    assert metadata.cube_name == "CubeX"
    assert metadata.image_number == 7
    assert metadata.suffix == "preview_out"
    assert metadata.path == "E:/projects/007_preview_out.png"
    assert metadata.source_key == ""
    assert metadata.source_label == "CubeX"
    assert metadata.scene_run_id == ""
    assert metadata.scene_key == ""
    assert metadata.scene_title == ""
    assert metadata.scene_order is None
    assert metadata.scene_count is None


def test_build_output_image_metadata_shortens_prefixed_source_label() -> None:
    """Fallback source labels should omit the model prefix from cube aliases."""

    service = CanvasIoService(image_repository=_repo())

    metadata = service.build_output_image_metadata(
        workflow_name="Recipe",
        node_meta_title="SDXL/Text to Image.KSampler",
        file_path=Path("E:/projects/008_output.png"),
    )

    assert metadata.cube_name == "SDXL/Text to Image"
    assert metadata.source_label == "Text to Image"


def test_build_output_image_metadata_preserves_scene_identity() -> None:
    """Metadata builder should carry explicit scene routing fields."""

    service = CanvasIoService(image_repository=_repo())

    metadata = service.build_output_image_metadata(
        workflow_name="Recipe",
        node_meta_title="CubeX.KSampler",
        file_path=Path("E:/projects/008_scene.png"),
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )

    assert metadata.scene_run_id == "run-1"
    assert metadata.scene_key == "portrait"
    assert metadata.scene_title == "Portrait"
    assert metadata.scene_order == 0
    assert metadata.scene_count == 2


def test_build_output_image_metadata_stores_resolution_and_cube_timing() -> None:
    """Metadata builder should carry output tooltip dimensions, slot, and timing."""

    service = CanvasIoService(image_repository=_repo())

    metadata = service.build_output_image_metadata(
        workflow_name="Recipe",
        node_meta_title="CubeX.KSampler",
        file_path=Path("E:/projects/009_scene.png"),
        node_id="save-node",
        width=1024,
        height=768,
        list_index=3,
        cube_execution_duration_ms=3080.0,
    )

    assert metadata.width == 1024
    assert metadata.height == 768
    assert metadata.node_id == "save-node"
    assert metadata.list_index == 3
    assert metadata.cube_execution_duration_ms == 3080.0


def test_open_images_in_external_editor_delegates_to_gateway() -> None:
    """External-editor multi-image open should delegate when gateway is configured."""

    calls: list[list[tuple[object, ImageMeta]]] = []

    def _open_images(*, images: list[tuple[object, ImageMeta]]) -> bool:
        calls.append(images)
        return True

    gateway = SimpleNamespace(
        open_image=lambda **_kwargs: True,
        open_images=_open_images,
    )
    service = CanvasIoService(image_repository=_repo(), external_image_gateway=gateway)
    images = [
        (
            object(),
            ImageMeta(
                workflow_name="",
                cube_name="",
                image_number=-1,
                suffix="",
                path="",
            ),
        )
    ]

    result = service.open_images_in_external_editor(images=images)

    assert result is True
    assert calls == [images]


def test_save_mask_image_delegates_to_image_repository() -> None:
    """Mask image saves should delegate to repository image persistence API."""

    captured_calls: list[tuple[Path, object]] = []

    def _save_image(path: Path, *, image: object) -> bool:
        captured_calls.append((path, image))
        return True

    service = CanvasIoService(image_repository=_repo(save_image=_save_image))
    destination = Path("E:/projects/Recipe/masks/mask.png")
    image_payload = object()

    saved = service.save_mask_image(destination=destination, image=image_payload)

    assert saved is True
    assert captured_calls == [(destination, image_payload)]


def test_save_mask_image_returns_false_when_repository_rejects_save() -> None:
    """Mask image save should return False when repository adapter save fails."""

    service = CanvasIoService(
        image_repository=_repo(save_image=lambda _path, *, image: image is None)
    )

    assert (
        service.save_mask_image(destination=Path("mask.png"), image=object()) is False
    )


def test_load_recipe_preview_image_delegates_to_image_repository() -> None:
    """Recipe preview loads should delegate to the image repository boundary."""

    calls: list[Path] = []
    preview = object()
    service = CanvasIoService(
        image_repository=_repo(load_image=lambda path: (calls.append(path), preview)[1])
    )
    path = Path("E:/projects/Recipe/recipe.png")

    loaded = service.load_recipe_preview_image(path)

    assert loaded is preview
    assert calls == [path]
