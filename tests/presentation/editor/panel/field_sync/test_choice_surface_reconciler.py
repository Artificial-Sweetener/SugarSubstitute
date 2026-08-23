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

"""Verify finite-choice changes reconcile existing editor controls in place."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication

from substitute.application.model_metadata import RichChoiceResolution
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    FieldPresentation,
    FieldValueSource,
    ResolvedFieldSpec,
)
from substitute.presentation.editor.panel.field_registry import EditorFieldRegistry
from substitute.presentation.editor.panel.field_state_controller import (
    EditorFieldBinding,
)
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshot,
    PanelModelChoiceSnapshotKind,
)
from substitute.presentation.editor.panel.choice_field_surface_reconciler import (
    ChoiceFieldSurfaceReconciler,
)
from substitute.presentation.editor.panel.widgets.fields.choice_combo import (
    EMPTY_CHOICE_PLACEHOLDER,
    EditorChoiceComboBox,
)
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.widgets.media_wall import unavailable_thumbnail_readiness


class _Picker:
    """Record in-place choice source replacement without constructing Qt."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Store field metadata and reconciliation calls."""

        self.metadata = metadata
        self.calls: list[tuple[object, str]] = []

    def property(self, name: str) -> object:
        """Return input metadata."""

        return self.metadata if name == "input_metadata" else None

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        """Replace input metadata."""

        if name == "input_metadata" and isinstance(value, dict):
            self.metadata = value

    def reconcile_choice_source(self, choice_source: object, value: str) -> None:
        """Record one silent in-place reconciliation."""

        self.calls.append((choice_source, value))


class _ChoiceSource:
    """Provide the prepared choice-source protocol required by snapshots."""

    def current_resolution(self) -> RichChoiceResolution:
        """Return one deterministic literal resolution."""

        return self._resolution()

    def refresh(self) -> RichChoiceResolution:
        """Return the same deterministic literal resolution."""

        return self._resolution()

    @staticmethod
    def _resolution() -> RichChoiceResolution:
        """Build one minimal rich-choice resolution."""

        return RichChoiceResolution(
            items=(),
            should_use_rich_picker=True,
            matched_kinds=("checkpoints",),
            option_count=1,
            enriched_count=0,
            ambiguous_count=0,
            unmatched_count=1,
            reason="test",
        )


class _SnapshotController:
    """Return a prepared picker snapshot for every model field."""

    def __init__(self) -> None:
        """Create a stable choice source."""

        self.choice_source = _ChoiceSource()

    def snapshot_for_field(self, _request: object) -> PanelModelChoiceSnapshot:
        """Return a consumable picker snapshot."""

        return PanelModelChoiceSnapshot(
            identity=CatalogSnapshotIdentity(source_revision=1),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            kind=PanelModelChoiceSnapshotKind.RICH_MODEL_PICKER,
            options=("only.safetensors",),
            model_kind="checkpoints",
            resolution=RichChoiceResolution(
                items=(),
                should_use_rich_picker=True,
                matched_kinds=("checkpoints",),
                option_count=1,
                enriched_count=0,
                ambiguous_count=0,
                unmatched_count=1,
                reason="test",
            ),
            choice_source=self.choice_source,
            thumbnail_readiness=unavailable_thumbnail_readiness("test"),
        )


class _ComboSnapshotController:
    """Keep ordinary finite choices on the combo presentation path."""

    def snapshot_for_field(self, _request: object) -> PanelModelChoiceSnapshot:
        """Return a disabled graphical-picker decision."""

        return PanelModelChoiceSnapshot(
            identity=CatalogSnapshotIdentity(source_revision=1),
            status=CatalogSnapshotStatus(
                CatalogSnapshotReadiness.DISABLED,
                unavailable_reason="ordinary_choice",
            ),
            kind=PanelModelChoiceSnapshotKind.NONE,
            thumbnail_readiness=unavailable_thumbnail_readiness("ordinary_choice"),
        )


def _field_spec(
    value: str,
    *,
    class_type: str = "CheckpointLoaderSimple",
    field_key: str = "ckpt_name",
    field_info: list[object] | None = None,
    value_source: FieldValueSource = FieldValueSource.FIRST_OPTION,
) -> ResolvedFieldSpec:
    """Return one resolved picker field."""

    return ResolvedFieldSpec(
        cube_alias="Cube",
        node_name="loader",
        class_type=class_type,
        field_key=field_key,
        field_type="COMBO",
        constraints={},
        meta_info={},
        field_info=(
            [["only.safetensors"], {"default": "only.safetensors"}]
            if field_info is None
            else field_info
        ),
        value=value,
        raw_value="",
        value_source=value_source,
        field_behavior=FieldBehavior(
            field_key=field_key,
            presentation=FieldPresentation.STANDARD,
        ),
    )


def _snapshot(spec: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Return a behavior snapshot containing one model field."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={"Cube": {"loader": {spec.field_key: spec}}},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def _binding(
    *,
    class_type: str = "CheckpointLoaderSimple",
    field_key: str = "ckpt_name",
) -> EditorFieldBinding:
    """Return one registered picker identity."""

    return EditorFieldBinding(
        cube_alias="Cube",
        node_name="loader",
        field_key=field_key,
        storage_kind="input",
        value_source="no_options",
        resolved_display_value="",
        prompt_field_identity=f"loader.{field_key}",
        node_type=class_type,
        field_type="COMBO",
    )


def test_option_change_updates_existing_picker_without_projection_rebuild() -> None:
    """An empty-to-one transition should keep widget identity and apply the sole value."""

    registry = EditorFieldRegistry()
    picker = _Picker(
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": "ckpt_name",
            "node_type": "CheckpointLoaderSimple",
            "type": "COMBO",
        }
    )
    registry.register(_binding(), picker)
    snapshot_controller = _SnapshotController()
    host = SimpleNamespace(
        node_definition_gateway=object(),
        _cube_states={
            "Cube": SimpleNamespace(
                buffer={
                    "nodes": {
                        "loader": {
                            "class_type": "CheckpointLoaderSimple",
                            "inputs": {"ckpt_name": "only.safetensors"},
                        }
                    }
                }
            )
        },
        _stack_order=["Cube"],
        current_behavior_snapshot=lambda: _snapshot(_field_spec("only.safetensors")),
    )
    reconciler = ChoiceFieldSurfaceReconciler(
        host=host,
        field_registry=registry,
        snapshot_controller=cast(object, snapshot_controller),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile(("CheckpointLoaderSimple",))

    assert result.reconciled_field_count == 1
    assert result.handled_node_classes == ("CheckpointLoaderSimple",)
    assert result.fallback_node_classes == ()
    assert picker.calls == [(snapshot_controller.choice_source, "only.safetensors")]
    assert registry.widget_map[("Cube", "loader", "ckpt_name")] is picker
    assert picker.metadata["resolved_value"] == "only.safetensors"
    assert picker.metadata["value_source"] == "first_option"


def test_missing_registered_model_field_requests_structural_fallback() -> None:
    """A newly introduced model control should rebuild only its affected surface."""

    host = SimpleNamespace(
        node_definition_gateway=object(),
        _cube_states={
            "Cube": SimpleNamespace(
                buffer={
                    "nodes": {
                        "loader": {
                            "class_type": "CheckpointLoaderSimple",
                            "inputs": {},
                        }
                    }
                }
            )
        },
        _stack_order=["Cube"],
        current_behavior_snapshot=lambda: _snapshot(_field_spec("only.safetensors")),
    )
    reconciler = ChoiceFieldSurfaceReconciler(
        host=host,
        field_registry=EditorFieldRegistry(),
        snapshot_controller=cast(object, _SnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile(("CheckpointLoaderSimple",))

    assert result.handled_node_classes == ()
    assert result.fallback_node_classes == ("CheckpointLoaderSimple",)


def test_vae_picker_reconciles_without_field_name_inference() -> None:
    """A catalog-qualified VAE picker should reconcile despite its generic field name."""

    class_type = "SimpleSyrup.SimpleLoadAnima"
    field_key = "vae"
    value = "qwen\\qwen-image-vae.safetensors"
    spec = _field_spec(
        value,
        class_type=class_type,
        field_key=field_key,
    )
    registry = EditorFieldRegistry()
    picker = _Picker(
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": field_key,
            "node_type": class_type,
            "type": "COMBO",
        }
    )
    registry.register(
        _binding(class_type=class_type, field_key=field_key),
        picker,
    )
    snapshot_controller = _SnapshotController()
    host = SimpleNamespace(
        node_definition_gateway=object(),
        _cube_states={
            "Cube": SimpleNamespace(
                buffer={
                    "nodes": {
                        "loader": {
                            "class_type": class_type,
                            "inputs": {field_key: value},
                        }
                    }
                }
            )
        },
        _stack_order=["Cube"],
        current_behavior_snapshot=lambda: _snapshot(spec),
    )
    reconciler = ChoiceFieldSurfaceReconciler(
        host=host,
        field_registry=registry,
        snapshot_controller=cast(object, snapshot_controller),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile((class_type,))

    assert result.reconciled_field_count == 1
    assert result.handled_node_classes == (class_type,)
    assert result.fallback_node_classes == ()
    assert picker.calls == [(snapshot_controller.choice_source, value)]


def test_upscaler_combo_reconciles_empty_to_populated_without_user_edit() -> None:
    """A discovered upscaler should appear immediately without replacing the control."""

    _application = QApplication.instance() or QApplication([])
    class_type = "UpscaleModelLoader"
    field_key = "model_name"
    available_model = "4x-AnimeSharp.pth"
    spec = _field_spec(
        available_model,
        class_type=class_type,
        field_key=field_key,
        field_info=["COMBO", {"options": [available_model]}],
    )
    combo = EditorChoiceComboBox()
    combo.setProperty(
        "input_metadata",
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": field_key,
            "node_type": class_type,
            "type": "COMBO",
        },
    )
    combo.reconcile_choice_items((), "")
    emitted_values: list[str] = []
    combo.currentTextChanged.connect(emitted_values.append)
    registry = EditorFieldRegistry()
    registry.register(_binding(class_type=class_type, field_key=field_key), combo)
    host = _host_for_spec(spec)
    reconciler = ChoiceFieldSurfaceReconciler(
        host=host,
        field_registry=registry,
        snapshot_controller=cast(object, _ComboSnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile((class_type,))

    assert result.fallback_node_classes == ()
    assert result.reconciled_field_count == 1
    assert registry.widget_map[("Cube", "loader", field_key)] is combo
    assert combo.isEnabled() is True
    assert combo.count() == 1
    assert combo.currentText() == available_model
    assert combo.placeholderText() == ""
    assert emitted_values == []
    combo.deleteLater()


def test_upscaler_combo_reconciles_populated_to_empty_without_fake_option() -> None:
    """Removing the last upscaler should leave a visible disabled empty control."""

    _application = QApplication.instance() or QApplication([])
    class_type = "UpscaleModelLoader"
    field_key = "model_name"
    spec = _field_spec(
        "",
        class_type=class_type,
        field_key=field_key,
        field_info=["COMBO", {"options": []}],
        value_source=FieldValueSource.NO_OPTIONS,
    )
    combo = EditorChoiceComboBox()
    combo.setProperty(
        "input_metadata",
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": field_key,
            "node_type": class_type,
            "type": "COMBO",
        },
    )
    combo.reconcile_choice_items((("old.pth", "old.pth"),), "old.pth")
    emitted_values: list[str] = []
    combo.currentTextChanged.connect(emitted_values.append)
    registry = EditorFieldRegistry()
    registry.register(_binding(class_type=class_type, field_key=field_key), combo)
    reconciler = ChoiceFieldSurfaceReconciler(
        host=_host_for_spec(spec),
        field_registry=registry,
        snapshot_controller=cast(object, _ComboSnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile((class_type,))

    assert result.fallback_node_classes == ()
    assert combo.isEnabled() is False
    assert combo.count() == 0
    assert combo.currentText() == ""
    assert combo.placeholderText() == EMPTY_CHOICE_PLACEHOLDER
    assert emitted_values == []
    combo.deleteLater()


def test_non_model_auto_sentinel_remains_a_real_selectable_choice() -> None:
    """A literal auto sentinel is populated choice state, not an empty fallback."""

    _application = QApplication.instance() or QApplication([])
    class_type = "SimpleSyrup.SimpleLoadAnima"
    field_key = "resolution"
    spec = _field_spec(
        "auto",
        class_type=class_type,
        field_key=field_key,
        field_info=[["auto"], {"default": "auto"}],
        value_source=FieldValueSource.EXPLICIT,
    )
    combo = EditorChoiceComboBox()
    combo.setProperty(
        "input_metadata",
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": field_key,
            "node_type": class_type,
            "type": "COMBO",
        },
    )
    registry = EditorFieldRegistry()
    registry.register(_binding(class_type=class_type, field_key=field_key), combo)
    reconciler = ChoiceFieldSurfaceReconciler(
        host=_host_for_spec(spec),
        field_registry=registry,
        snapshot_controller=cast(object, _ComboSnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile((class_type,))

    assert result.fallback_node_classes == ()
    assert combo.isEnabled() is True
    assert combo.count() == 1
    assert combo.currentText() == "auto"
    combo.deleteLater()


@pytest.mark.parametrize(
    ("options", "resolved_value"),
    (
        (["old.pth", "new.pth"], "old.pth"),
        (["replacement.pth"], "replacement.pth"),
    ),
    ids=("still-valid-selection", "removed-selection"),
)
def test_changed_upscaler_options_follow_application_resolution_without_signal(
    options: list[str],
    resolved_value: str,
) -> None:
    """Changed options must preserve or replace selection exactly as resolved upstream."""

    _application = QApplication.instance() or QApplication([])
    class_type = "UpscaleModelLoader"
    field_key = "model_name"
    spec = _field_spec(
        resolved_value,
        class_type=class_type,
        field_key=field_key,
        field_info=["COMBO", {"options": options}],
    )
    combo = EditorChoiceComboBox()
    combo.setProperty(
        "input_metadata",
        {
            "cube_alias": "Cube",
            "node_name": "loader",
            "key": field_key,
            "node_type": class_type,
            "type": "COMBO",
        },
    )
    combo.reconcile_choice_items((("old.pth", "old.pth"),), "old.pth")
    emitted_values: list[str] = []
    combo.currentTextChanged.connect(emitted_values.append)
    registry = EditorFieldRegistry()
    registry.register(_binding(class_type=class_type, field_key=field_key), combo)
    host = _host_for_spec(spec)
    reconciler = ChoiceFieldSurfaceReconciler(
        host=host,
        field_registry=registry,
        snapshot_controller=cast(object, _ComboSnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile((class_type,))

    assert result.fallback_node_classes == ()
    assert combo.currentText() == resolved_value
    assert [combo.itemText(index) for index in range(combo.count())] == options
    assert emitted_values == []
    cube_state = host._cube_states["Cube"]
    assert cube_state.buffer["nodes"]["loader"]["inputs"][field_key] == resolved_value
    combo.deleteLater()


def _host_for_spec(spec: ResolvedFieldSpec) -> SimpleNamespace:
    """Return a panel host containing one finite-choice field."""

    return SimpleNamespace(
        node_definition_gateway=object(),
        _cube_states={
            "Cube": SimpleNamespace(
                buffer={
                    "nodes": {
                        "loader": {
                            "class_type": spec.class_type,
                            "inputs": {spec.field_key: spec.value},
                        }
                    }
                }
            )
        },
        _stack_order=["Cube"],
        current_behavior_snapshot=lambda: _snapshot(spec),
    )
