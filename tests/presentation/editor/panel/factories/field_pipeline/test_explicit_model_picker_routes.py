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

"""Verify explicit model-picker presentation routes."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations
from typing import Callable, cast
import pytest
from PySide6.QtWidgets import QWidget
from substitute.application.model_metadata import (
    ThumbnailAssetRepository,
)
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
import substitute.presentation.editor.panel.factories.field_pipeline as factories
from substitute.presentation.widgets.model_picker import (
    ModelPickerThumbnailPreloadRoute,
)
from ..choice.characterization_support import (
    _FakeModelCatalog,
    _FakeModelPickerField,
    _FakePromptAutocompleteGateway,
    _model_choice_controller,
    _model_item,
    _rich_choice_resolver,
    _wildcard_gateway,
)


def test_build_widget_for_field_behavior_builds_model_picker_from_presentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MODEL_PICKER presentation should build the explicit model picker field."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    model_catalog = _FakeModelCatalog(
        (_model_item("checkpoints", "models/base.safetensors", "Civit Base"),)
    )
    thumbnail_repository = cast(ThumbnailAssetRepository, object())
    thumbnail_route_factory = cast(
        Callable[[QWidget], ModelPickerThumbnailPreloadRoute], object()
    )

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(
            field_key="ckpt_name",
            presentation=FieldPresentation.MODEL_PICKER,
            style={"model_kind": "checkpoints"},
        ),
        node_name="checkpoint",
        key="ckpt_name",
        value="models/base.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=_model_choice_controller(model_catalog),
        thumbnail_asset_repository=thumbnail_repository,
        model_picker_thumbnail_preload_route_factory=thumbnail_route_factory,
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.parent == "parent"
    assert widget.resolution.matched_kinds == ("checkpoints",)
    assert widget.thumbnail_asset_repository is thumbnail_repository
    assert widget.thumbnail_preload_route_factory is thumbnail_route_factory
    assert widget.currentText() == "models/base.safetensors"
    assert model_catalog.list_calls == []


def test_explicit_model_picker_reuses_shared_rich_choice_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MODEL_PICKER fields should consume prepared snapshots without catalog loading."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    model_catalog = _FakeModelCatalog(
        (
            _model_item("checkpoints", "models/base.safetensors", "Civit Base"),
            _model_item("checkpoints", "models/refiner.safetensors", "Refiner"),
        )
    )
    resolver = _rich_choice_resolver(model_catalog)
    controller = _model_choice_controller(model_catalog, resolver)
    behavior = FieldBehavior(
        field_key="ckpt_name",
        presentation=FieldPresentation.MODEL_PICKER,
        style={"model_kind": "checkpoints"},
    )

    first_widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=behavior,
        node_name="checkpoint",
        key="ckpt_name",
        value="models/base.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=controller,
    )
    second_widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=behavior,
        node_name="checkpoint",
        key="ckpt_name",
        value="models/refiner.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=_wildcard_gateway(),
        model_choice_snapshot_controller=controller,
    )

    assert isinstance(first_widget, _FakeModelPickerField)
    assert isinstance(second_widget, _FakeModelPickerField)
    assert [item.value for item in first_widget.resolution.items] == [
        "models/base.safetensors",
        "models/refiner.safetensors",
    ]
    assert [item.value for item in second_widget.resolution.items] == [
        "models/base.safetensors",
        "models/refiner.safetensors",
    ]
    assert model_catalog.list_calls == []
