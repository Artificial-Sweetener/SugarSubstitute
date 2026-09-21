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

"""Render the production Ultralytics picker through a cube wrapper field."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import FieldBehavior
from substitute.infrastructure.model_thumbnails import (
    BundledUltralyticsThumbnailRepository,
)
from substitute.application.model_metadata.ultralytics_thumbnail_associations import (
    UltralyticsThumbnailAssociationService,
)
from substitute.infrastructure.persistence.file_ultralytics_thumbnail_association_repository import (
    FileUltralyticsThumbnailAssociationRepository,
)
from substitute.presentation.editor.panel.factories.field_pipeline import (
    build_widget_for_field_behavior,
)
from substitute.presentation.dialogs.ultralytics_thumbnail_library_modal import (
    UltralyticsThumbnailLibraryModal,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataMenuAction,
)
from tests.presentation.editor.panel.factories.choice.characterization_support import (
    _FakeModelCatalog,
    _FakePromptAutocompleteGateway,
    _model_choice_controller,
    _wildcard_gateway,
)
from tests.presentation.widgets.model_picker.support import (
    _thumbnail_preload_route_factory,
    _wait_for_thumbnail_preloader_idle,
    ensure_qapp,
)
from tests.presentation.widgets.model_picker.popup_fixtures import (
    _MetadataActionHandler,
)
from tests.support.qt.lifecycle import destroy_qt_object

_AUTOMASK_WRAPPER_TYPE = "c6bb854c-c2ee-47a7-818d-f51684b83e0a"


def test_automask_wrapper_renders_ultralytics_thumbnail_grid(
    tmp_path: Path,
) -> None:
    """The real wrapper provenance should render friendly visual model choices."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(760, 700)
    layout = QVBoxLayout(host)
    options = [
        "bbox/Anzhcs ManFace v02 1024 y8n.pt",
        "bbox/Anzhcs WomanFace v05 1024 y8n.pt",
        "bbox/Eyes.pt",
        "segm/Anzhc Face 1024 v2 y8n.pt",
        "Bingsu Face YOLOv8n v2 (6.23MB)",
        "Bingsu Person YOLOv8n-seg (6.78MB)",
    ]
    metadata_action_handler = _MetadataActionHandler()
    thumbnail_associations = UltralyticsThumbnailAssociationService(
        FileUltralyticsThumbnailAssociationRepository(tmp_path)
    )
    field = build_widget_for_field_behavior(
        parent=host,
        field_behavior=FieldBehavior(field_key="model_name"),
        node_name="detect_segs_w_ultralytics",
        key="model_name",
        value=options[0],
        field_meta={
            "cube_alias": "SDXL/Automask Detailer",
            "body_node_type": "SimpleSyrup.LoadUltralyticsModel",
            "body_input_name": "model_name",
        },
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(
            _FakeModelCatalog(()),
            ultralytics_thumbnail_associations=thumbnail_associations,
        ),
        thumbnail_asset_repository=BundledUltralyticsThumbnailRepository(),
        model_metadata_action_handler=metadata_action_handler,
        model_picker_thumbnail_preload_route_factory=(
            _thumbnail_preload_route_factory()
        ),
        field_type="LIST",
        node_type=_AUTOMASK_WRAPPER_TYPE,
        field_info=[options, {}],
    )
    assert isinstance(field, ModelPickerField)
    layout.addWidget(field)
    host.show()
    app.processEvents()
    assert field._thumbnail_preloader is not None
    assert _wait_for_thumbnail_preloader_idle(field._thumbnail_preloader, 1_000)

    closed_render = host.grab().toImage()
    _assert_rendered(closed_render, tmp_path / "ultralytics-field.png")
    assert field._surface._should_paint_closed_banner_decoration() is True
    assert field.displayText() == "Anzhcs ManFace v02 1024 y8n"
    assert field.currentText() == options[0]
    thumbnail_associations.assign(options[0], "hand-segmentation")
    field.refresh_metadata()
    assert (
        field._item_by_backend_value[options[0]].thumbnail_variants[0].storage_key
        == "bundled:ultralytics:hand-segmentation"
    )
    closed_target = field._metadata_context_menu_target_for_current_value()
    assert closed_target is not None
    assert closed_target.model_kind == "ultralytics"
    closed_actions = field._metadata_context_menu.menu_items_for_target(closed_target)
    assert [
        action.label
        for action in closed_actions
        if isinstance(action, ModelMetadataMenuAction)
    ] == ["Choose detector thumbnail"]

    field.open_picker()
    app.processEvents()
    popup = field._popup
    assert popup is not None and popup.isVisible()
    popup.resize(760, 640)
    for _ in range(4):
        app.processEvents()
    picker_items = field._picker_items
    assert [item.backend_value for item in picker_items] == options
    assert [item.title for item in picker_items] == [
        "Anzhcs ManFace v02 1024 y8n",
        "Anzhcs WomanFace v05 1024 y8n",
        "Eyes",
        "Anzhc Face 1024 v2 y8n",
        "Bingsu Face YOLOv8n v2",
        "Bingsu Person YOLOv8n-seg",
    ]
    assert all(item.thumbnail_variants for item in picker_items)
    assert (
        picker_items[3].thumbnail_variants[0].storage_key
        == "bundled:ultralytics:face-segmentation"
    )
    wall_target = popup._view._metadata_context_menu_target(picker_items[0])
    assert wall_target is not None
    wall_actions = popup._view._metadata_context_menu.menu_items_for_target(wall_target)
    assert [
        action.label
        for action in wall_actions
        if isinstance(action, ModelMetadataMenuAction)
    ] == ["Choose detector thumbnail"]
    _assert_rendered(
        popup.grab().toImage(),
        tmp_path / "ultralytics-grid.png",
    )
    popup_visibility_at_library_open: list[bool] = []

    def open_auto_closing_library() -> None:
        """Exercise native modal entry after the attached popup is hidden."""

        popup_visibility_at_library_open.append(popup.isVisible())
        modal = UltralyticsThumbnailLibraryModal(
            asset_repository=BundledUltralyticsThumbnailRepository(),
            model_display_name=wall_target.display_label(),
        )
        assert modal.modal_owner is host
        QTimer.singleShot(0, modal.reject)
        assert modal.exec() == modal.DialogCode.Rejected

    metadata_action_handler.before_ultralytics_choice = open_auto_closing_library
    library_action = next(
        action for action in wall_actions if isinstance(action, ModelMetadataMenuAction)
    )
    library_action.callback()
    assert popup.isVisible() is False
    assert popup_visibility_at_library_open == []
    assert metadata_action_handler.ultralytics_targets == []
    app.processEvents()
    assert popup_visibility_at_library_open == [False]
    assert metadata_action_handler.ultralytics_targets == [wall_target]
    destroy_qt_object(host)


def _assert_rendered(image: QImage, path: Path) -> None:
    """Assert that a widget render is nonempty and persist it for test diagnosis."""

    assert not image.isNull()
    assert image.width() > 200
    assert image.height() > 30
    assert image.save(str(path)) is True
    assert path.stat().st_size > 1_000
