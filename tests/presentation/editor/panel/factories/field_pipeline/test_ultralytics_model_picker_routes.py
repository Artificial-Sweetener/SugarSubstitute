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

"""Verify normal and cube Ultralytics fields use the shared model picker."""

from __future__ import annotations

import pytest

from substitute.application.node_behavior import FieldBehavior
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
import substitute.presentation.editor.panel.factories.field_pipeline as factories
from tests.presentation.editor.panel.factories.choice.characterization_support import (
    _FakeModelCatalog,
    _FakeModelPickerField,
    _FakePromptAutocompleteGateway,
    _model_choice_controller,
    _wildcard_gateway,
)


class _EmptyThumbnailAssetRepository:
    """Represent an available repository without test-owned image bytes."""

    def read_thumbnail_asset(self, storage_key: str) -> None:
        """Return no asset for the requested key."""

        _ = storage_key
        return None


@pytest.mark.parametrize(
    ("node_type", "field_meta"),
    (
        ("SimpleSyrup.LoadUltralyticsModel", {}),
        ("UltralyticsDetectorProvider", {}),
        (
            "c6bb854c-c2ee-47a7-818d-f51684b83e0a",
            {
                "cube_alias": "SDXL/Automask Detailer",
                "body_node_type": "SimpleSyrup.LoadUltralyticsModel",
                "body_input_name": "model_name",
            },
        ),
        (
            "3f33e532-9a3f-40e8-ac9d-df3c42b4512a",
            {
                "cube_alias": "Anima/Automask Detailer",
                "body_node_type": "SimpleSyrup.LoadUltralyticsModel",
                "body_input_name": "model_name",
            },
        ),
    ),
)
def test_ultralytics_fields_build_visual_picker_from_live_choices(
    monkeypatch: pytest.MonkeyPatch,
    node_type: str,
    field_meta: dict[str, object],
) -> None:
    """Normal and cube projections should share exact-value visual enrichment."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(())
    repository = _EmptyThumbnailAssetRepository()
    options = [
        "bbox/face_yolov8n.pt",
        "Bingsu Person YOLOv8n-seg (6.78MB)",
    ]

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="model_name"),
        node_name="ultralytics_loader",
        key="model_name",
        value=options[0],
        field_meta=field_meta,
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(catalog),
        thumbnail_asset_repository=repository,
        field_type="LIST",
        node_type=node_type,
        field_info=[options, {}],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.thumbnail_asset_repository is repository
    assert [item.value for item in widget.resolution.items] == options
    assert [
        item.thumbnail_variants[0].storage_key for item in widget.resolution.items
    ] == [
        "bundled:ultralytics:face-detection",
        "bundled:ultralytics:person-segmentation",
    ]
