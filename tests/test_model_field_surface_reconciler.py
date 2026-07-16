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

"""Verify model option changes reconcile existing editor controls in place."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

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
from substitute.presentation.editor.panel.model_field_surface_reconciler import (
    ModelFieldSurfaceReconciler,
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
            kind=PanelModelChoiceSnapshotKind.LITERAL_MODEL_PICKER,
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


def _field_spec(value: str) -> ResolvedFieldSpec:
    """Return one resolved checkpoint picker field."""

    return ResolvedFieldSpec(
        cube_alias="Cube",
        node_name="loader",
        class_type="CheckpointLoaderSimple",
        field_key="ckpt_name",
        field_type="COMBO",
        constraints={},
        meta_info={},
        field_info=[["only.safetensors"], {"default": "only.safetensors"}],
        value=value,
        raw_value="",
        value_source=FieldValueSource.FIRST_OPTION,
        field_behavior=FieldBehavior(
            field_key="ckpt_name",
            presentation=FieldPresentation.STANDARD,
        ),
    )


def _snapshot(spec: ResolvedFieldSpec) -> EditorBehaviorSnapshot:
    """Return a behavior snapshot containing one model field."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={"Cube": {"loader": {"ckpt_name": spec}}},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def _binding() -> EditorFieldBinding:
    """Return the registered checkpoint picker identity."""

    return EditorFieldBinding(
        cube_alias="Cube",
        node_name="loader",
        field_key="ckpt_name",
        storage_kind="input",
        value_source="no_options",
        resolved_display_value="",
        prompt_field_identity="loader.ckpt_name",
        node_type="CheckpointLoaderSimple",
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
    reconciler = ModelFieldSurfaceReconciler(
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
    reconciler = ModelFieldSurfaceReconciler(
        host=host,
        field_registry=EditorFieldRegistry(),
        snapshot_controller=cast(object, _SnapshotController()),
        thumbnail_repository_available=False,
    )

    result = reconciler.reconcile(("CheckpointLoaderSimple",))

    assert result.handled_node_classes == ()
    assert result.fallback_node_classes == ("CheckpointLoaderSimple",)
