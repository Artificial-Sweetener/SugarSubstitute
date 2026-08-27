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

"""Widget tests for the cube stack cart modal."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.application.cubes import (
    CubePickerClassification,
    CubePickerRole,
    CubeStackDraftEntry,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.domain.cube_library import CubeSourceMetadata
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    CubeStackCartModal,
)


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _IconFactory:
    """Return blank Qt icons for modal tests."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> QIcon:
        """Return a blank icon."""

        _ = (
            cube_id,
            display_name,
            icon,
            catalog_revision,
            cube_content_hash,
            render_size,
        )
        return QIcon()


def _six_catalog_records() -> list[CubeCatalogRecord]:
    """Return a representative six-cube catalog for cart modal tests."""

    return [
        CubeCatalogRecord(
            cube_id="image-to-image", version="1.0.0", display_name="Image to Image"
        ),
        CubeCatalogRecord(cube_id="inpaint", version="1.0.0", display_name="Inpaint"),
        CubeCatalogRecord(
            cube_id="text-to-image", version="1.0.0", display_name="Text to Image"
        ),
        CubeCatalogRecord(
            cube_id="automask-detailer",
            version="1.0.0",
            display_name="Automask Detailer",
        ),
        CubeCatalogRecord(
            cube_id="diffusion-upscale",
            version="1.0.0",
            display_name="Diffusion Upscale",
        ),
        CubeCatalogRecord(
            cube_id="promptmask-detailer",
            version="1.0.0",
            display_name="Promptmask Detailer",
        ),
    ]


def _six_catalog_classifications() -> dict[str, CubePickerClassification]:
    """Return start/middle roles for the representative catalog."""

    return {
        "image-to-image": _classification("start", 0, 1),
        "inpaint": _classification("start", 0, 1),
        "text-to-image": _classification("start", 0, 1),
        "automask-detailer": _classification("middle", 1, 1),
        "diffusion-upscale": _classification("middle", 1, 1),
        "promptmask-detailer": _classification("middle", 1, 1),
    }


def _pack_catalog_records() -> list[CubeCatalogRecord]:
    """Return catalog records with varied source packs for view-mode tests."""

    return [
        CubeCatalogRecord(
            cube_id="SDXL/base-start.cube",
            version="1.0.0",
            display_name="Base Start",
            source=_source(repo_ref="Example/Base"),
            supported_models=("SDXL 1.0", "SD 1.5"),
        ),
        CubeCatalogRecord(
            cube_id="SDXL/base-middle.cube",
            version="1.0.0",
            display_name="Base Middle",
            source=_source(repo_ref="Example/Base"),
            supported_models=("SDXL 1.0",),
        ),
        CubeCatalogRecord(
            cube_id="Flux/local-refiner.cube",
            version="1.0.0",
            display_name="Local Refiner",
            source=_source(kind="local"),
            supported_models=("Flux .1 D",),
        ),
        CubeCatalogRecord(
            cube_id="unknown-start",
            version="1.0.0",
            display_name="Unknown Start",
        ),
    ]


def _pack_catalog_classifications() -> dict[str, CubePickerClassification]:
    """Return role classifications for the pack-view fixture."""

    return {
        "SDXL/base-start.cube": _classification("start", 0, 1),
        "SDXL/base-middle.cube": _classification("middle", 1, 1),
        "Flux/local-refiner.cube": _classification("middle", 1, 1),
        "unknown-start": _classification("start", 0, 1),
    }


def _source(
    *,
    kind: str = "github",
    repo_ref: str = "",
) -> CubeSourceMetadata:
    """Return source metadata for modal tests."""

    return CubeSourceMetadata(kind=kind, repo_ref=repo_ref, path="")


def _classification(
    role: CubePickerRole,
    inputs: int,
    outputs: int,
) -> CubePickerClassification:
    """Return one picker role classification."""

    return CubePickerClassification(
        role=role,
        input_count=inputs,
        output_count=outputs,
    )


def _draft_entries(count: int) -> tuple[CubeStackDraftEntry, ...]:
    """Return existing draft entries for representative cart tests."""

    return tuple(
        CubeStackDraftEntry(
            draft_id=f"existing:Cube {index}",
            source="existing",
            cube_id=f"cube-existing-{index}",
            display_name=f"Cube {index}",
            secondary_text="v1.0.0 - base-cubes",
            icon=None,
            existing_alias=f"Cube {index}",
        )
        for index in range(count)
    )


def _visible_label_texts(root: QWidget) -> list[str]:
    """Return non-empty visible label text from one widget subtree."""

    return [
        label.text()
        for label in root.findChildren(QLabel)
        if label.isVisible() and label.text()
    ]


def _all_label_texts(root: QWidget) -> list[str]:
    """Return non-empty label text from one widget subtree."""

    return [label.text() for label in root.findChildren(QLabel) if label.text()]


def _result_layout_label_texts(modal: CubeStackCartModal) -> list[str]:
    """Return non-empty section labels from the active result layout."""

    labels: list[str] = []
    for index in range(modal._results_layout.count()):
        item = modal._results_layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if isinstance(widget, QLabel) and widget.text():
            labels.append(widget.text())
            continue
        if widget is not None:
            labels.extend(
                label.text() for label in widget.findChildren(QLabel) if label.text()
            )
    return labels


def _rendered_cube_ids(modal: CubeStackCartModal) -> list[str]:
    """Return cube IDs for rendered library cards, including repeated cards."""

    return [card.cube_id for card in modal._cards.values()]


def _clear_override_cursor() -> None:
    """Clear override cursors left by focused cursor-feedback tests."""

    while QApplication.overrideCursor() is not None:
        QApplication.restoreOverrideCursor()
