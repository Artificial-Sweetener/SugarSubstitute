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

"""Tests for compatibility-aware discovery routing from empty model pickers."""

from __future__ import annotations

from typing import Any, cast

import pytest

from substitute.application.model_metadata import ModelCatalogSnapshot
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.application.model_metadata import (
    ModelChoiceCatalogIndex,
    RichChoiceResolver,
)
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.domain.model_suggestions import ModelSuggestionContext
from substitute.presentation.editor.panel.factories.choice_factory import (
    ChoiceFieldBuildRequest,
    ChoiceFieldFactory,
)
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)
from substitute.presentation.editor.panel.model_choice_snapshots import (
    PanelModelChoiceSnapshot,
    PanelModelChoiceSnapshotRequest,
)


class _FakeModelPickerField:
    """Capture the discovery action constructed for one picker."""

    def __init__(
        self,
        parent: object = None,
        *,
        choice_source: Any,
        current_value: str = "",
        empty_model_action: object | None = None,
        **_kwargs: object,
    ) -> None:
        """Store only state exercised by discovery routing."""

        self.parent = parent
        self.choice_source = choice_source
        self.current_value = current_value
        self.empty_model_action = empty_model_action

    def currentText(self) -> str:
        """Return the exact backend value."""

        return self.current_value

    def setCurrentText(self, value: str) -> None:
        """Accept the exact installed backend value."""

        self.current_value = value


class _EmptyWarmCatalog:
    """Expose an authoritative warm, empty model catalog."""

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot:
        """Return one warm empty snapshot."""

        return ModelCatalogSnapshot(kind=kind, items=(), generation=1)


def _empty_snapshot(
    *, target_model: str
) -> tuple[FieldBehavior, PanelModelChoiceSnapshot]:
    """Prepare an explicit empty diffusion-model picker snapshot."""

    behavior = FieldBehavior(
        field_key="unet_name",
        presentation=FieldPresentation.MODEL_PICKER,
        style={"model_kind": "diffusion_models"},
    )
    snapshot = PanelModelChoiceSnapshotController(
        model_catalog_service=cast(Any, _EmptyWarmCatalog()),
        model_choice_resolver=None,
    ).snapshot_for_field(
        PanelModelChoiceSnapshotRequest(
            field_behavior=behavior,
            node_name="loader",
            key="unet_name",
            value="",
            node_type="",
            field_type=None,
            field_info=None,
            node_definition_gateway=None,
            target_model=target_model,
        )
    )
    return behavior, snapshot


def test_empty_compatible_picker_routes_discovery_result_to_exact_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warm empty picker should expose discovery and accept its backend value."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    behavior, snapshot = _empty_snapshot(target_model="Anima")
    requests: list[ModelSuggestionContext] = []

    def discover(context: ModelSuggestionContext, receiver: object) -> None:
        """Record compatibility and publish one installed backend value."""

        requests.append(context)
        assert callable(receiver)
        receiver("Anima/installed.safetensors")

    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent="parent",
            field_behavior=behavior,
            node_name="loader",
            key="unet_name",
            value="",
            field_meta={},
            model_choice_snapshot=snapshot,
            empty_model_picker_action=discover,
        )
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert callable(widget.empty_model_action)
    widget.empty_model_action()
    assert requests[0].family_id is ModelFamilyId.ANIMA
    assert widget.currentText() == "Anima/installed.safetensors"


def test_empty_picker_without_compatible_family_has_no_discovery_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage kind alone must never guess a model-family compatibility contract."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    behavior, snapshot = _empty_snapshot(target_model="SDXL")
    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent="parent",
            field_behavior=behavior,
            node_name="loader",
            key="unet_name",
            value="",
            field_meta={},
            model_choice_snapshot=snapshot,
            empty_model_picker_action=lambda _context, _receiver: None,
        )
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.empty_model_action is None


def test_empty_standard_anima_field_builds_discovery_picker_from_real_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production Anima field must remain identifiable with zero options."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _EmptyWarmCatalog()
    resolver = RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=cast(Any, catalog))
    )
    controller = PanelModelChoiceSnapshotController(
        model_catalog_service=cast(Any, catalog),
        model_choice_resolver=resolver,
    )
    behavior = FieldBehavior(field_key="diffusion_model")
    snapshot = controller.snapshot_for_field(
        PanelModelChoiceSnapshotRequest(
            field_behavior=behavior,
            node_name="models",
            key="diffusion_model",
            value="",
            node_type="SimpleSyrup.SimpleLoadAnima",
            field_type="LIST",
            field_info=[[], {}],
            node_definition_gateway=None,
            target_model="Anima",
        )
    )
    requests: list[ModelSuggestionContext] = []

    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent="parent",
            field_behavior=behavior,
            node_name="models",
            key="diffusion_model",
            value="",
            field_meta={},
            model_choice_snapshot=snapshot,
            empty_model_picker_action=lambda context, _receiver: requests.append(
                context
            ),
            node_type="SimpleSyrup.SimpleLoadAnima",
            field_type="LIST",
            field_info=[[], {}],
        )
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert snapshot.model_kind == "diffusion_models"
    assert snapshot.suggestion_context is not None
    assert callable(widget.empty_model_action)
    widget.empty_model_action()
    assert requests == [snapshot.suggestion_context]
