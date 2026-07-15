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

"""Define prepared catalog snapshot contracts for editor foreground consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)


class CatalogLookupClassification(StrEnum):
    """Classify existing catalog work before Phase 23 moves ownership."""

    BACKGROUND_WARMUP = "background_warmup"
    EXPLICIT_REFRESH = "explicit_refresh"
    FORBIDDEN_FOREGROUND = "forbidden_foreground"


class CatalogForegroundConsumer(StrEnum):
    """Name catalog-backed foreground consumers covered by Phase 23."""

    LORA_PICKER = "lora_picker"
    LORA_TRIGGER_WORD_ACTIONS = "lora_trigger_word_actions"
    PROMPT_SEGMENT_PRESETS = "prompt_segment_presets"
    WILDCARD_AUTOCOMPLETE = "wildcard_autocomplete"
    PANEL_MODEL_CHOICES = "panel_model_choices"
    EXPLICIT_MODEL_PICKER = "explicit_model_picker"
    ACTIVE_MODEL_PRESET_CONTEXT = "active_model_preset_context"
    DIMENSION_PRESET_MENU = "dimension_preset_menu"
    NODE_INPUT_PRESET_MENU = "node_input_preset_menu"
    THUMBNAIL_READINESS = "thumbnail_readiness"


@dataclass(frozen=True, slots=True)
class CatalogForegroundPathInventoryItem:
    """Assign one current catalog lookup path to an owner and Phase 23 sub-phase."""

    consumer: CatalogForegroundConsumer
    current_path: str
    lookup_token: str
    classification: CatalogLookupClassification
    snapshot_owner: str
    sub_phase: str
    baseline_test: str

    def __post_init__(self) -> None:
        """Reject incomplete inventory rows before later sub-phases rely on them."""

        required_values = (
            self.current_path,
            self.lookup_token,
            self.snapshot_owner,
            self.sub_phase,
            self.baseline_test,
        )
        if any(not value.strip() for value in required_values):
            raise ValueError("catalog foreground inventory rows must be complete.")
        if not self.sub_phase.startswith("23."):
            raise ValueError("Phase 23 inventory rows must name a 23.x sub-phase.")


PHASE23_CATALOG_FOREGROUND_INVENTORY: tuple[CatalogForegroundPathInventoryItem, ...] = (
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.LORA_PICKER,
        current_path="prompt_editor/features/lora_picker_snapshots.py",
        lookup_token="refresh_loras(",
        classification=CatalogLookupClassification.EXPLICIT_REFRESH,
        snapshot_owner="features/lora_picker_snapshots.py::PromptLoraPickerSnapshotController",
        sub_phase="23.2",
        baseline_test="tests/test_prompt_lora_metadata_controller.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.LORA_PICKER,
        current_path="prompt_editor/features/lora_picker_snapshots.py",
        lookup_token="list_loras(",
        classification=CatalogLookupClassification.EXPLICIT_REFRESH,
        snapshot_owner="features/lora_picker_snapshots.py::PromptLoraPickerSnapshotController",
        sub_phase="23.2",
        baseline_test="tests/test_prompt_lora_metadata_controller.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.LORA_TRIGGER_WORD_ACTIONS,
        current_path="prompt_editor/features/lora_action_snapshots.py",
        lookup_token="cached_context_snapshot(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="features/lora_action_snapshots.py::PromptLoraTriggerWordProjector",
        sub_phase="23.3",
        baseline_test="tests/test_prompt_lora_metadata_controller.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.PROMPT_SEGMENT_PRESETS,
        current_path="prompt_editor/features/prompt_segment_preset_source.py",
        lookup_token="list_prompt_segment_presets(",
        classification=CatalogLookupClassification.EXPLICIT_REFRESH,
        snapshot_owner="features/prompt_segment_preset_models.py::PromptSegmentPresetSnapshot",
        sub_phase="23.4",
        baseline_test="tests/test_prompt_segment_preset_controller.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.WILDCARD_AUTOCOMPLETE,
        current_path="prompt_editor/features/wildcard_controller.py",
        lookup_token="search_wildcards(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="features/catalog_snapshots.py::Wildcard autocomplete snapshot owner",
        sub_phase="23.5",
        baseline_test="tests/test_prompt_wildcard_feature_controller.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.PANEL_MODEL_CHOICES,
        current_path="panel/factories/choice_factory.py",
        lookup_token="model_choice_resolver.resolve(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/model_choice_snapshot_controller.py",
        sub_phase="23.6",
        baseline_test="tests/test_panel_choice_factory.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.PANEL_MODEL_CHOICES,
        current_path="panel/factories/choice_factory.py",
        lookup_token="model_choice_resolver.refresh(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/model_choice_snapshot_controller.py",
        sub_phase="23.6",
        baseline_test="tests/test_panel_choice_factory.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.EXPLICIT_MODEL_PICKER,
        current_path="panel/factories/choice_factory.py",
        lookup_token="model_catalog_service.list_models(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/model_choice_snapshot_controller.py",
        sub_phase="23.6",
        baseline_test="tests/test_panel_choice_factory.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.EXPLICIT_MODEL_PICKER,
        current_path="panel/factories/choice_factory.py",
        lookup_token="ModelChoiceCatalogIndex(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/model_choice_snapshot_controller.py",
        sub_phase="23.6",
        baseline_test="tests/test_panel_choice_factory.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.ACTIVE_MODEL_PRESET_CONTEXT,
        current_path="panel/context/active_model_snapshot.py",
        lookup_token="matching_catalog_item(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/context/active_model_snapshot.py",
        sub_phase="23.7",
        baseline_test="tests/test_active_model_context.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.DIMENSION_PRESET_MENU,
        current_path="panel/menus/dimension_preset_menu_source.py",
        lookup_token="prepare_dimension_preset_menu_model(",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/menus/dimension_preset_menu_source.py",
        sub_phase="23.7",
        baseline_test="tests/test_dimension_preset_menu_source.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.NODE_INPUT_PRESET_MENU,
        current_path="panel/menus/node_input_preset_menu_source.py",
        lookup_token="active_model_snapshots.snapshot",
        classification=CatalogLookupClassification.FORBIDDEN_FOREGROUND,
        snapshot_owner="panel/context/active_model_snapshot.py",
        sub_phase="23.7",
        baseline_test="tests/test_node_input_preset_menu_source.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.THUMBNAIL_READINESS,
        current_path="prompt_editor/async_work/thumbnail_preloader.py",
        lookup_token="read_thumbnail_asset(",
        classification=CatalogLookupClassification.BACKGROUND_WARMUP,
        snapshot_owner="features/catalog_snapshots.py::Thumbnail readiness snapshot owner",
        sub_phase="23.8",
        baseline_test="tests/test_prompt_lora_thumbnail_preloader.py",
    ),
    CatalogForegroundPathInventoryItem(
        consumer=CatalogForegroundConsumer.THUMBNAIL_READINESS,
        current_path="prompt_editor/async_work/thumbnail_preloader.py",
        lookup_token="image_from_qt_thumbnail_payload(",
        classification=CatalogLookupClassification.BACKGROUND_WARMUP,
        snapshot_owner="features/catalog_snapshots.py::Thumbnail readiness snapshot owner",
        sub_phase="23.8",
        baseline_test="tests/test_prompt_lora_thumbnail_preloader.py",
    ),
)


__all__ = [
    "CatalogForegroundConsumer",
    "CatalogForegroundPathInventoryItem",
    "CatalogLookupClassification",
    "CatalogSnapshotIdentity",
    "CatalogSnapshotReadiness",
    "CatalogSnapshotStatus",
    "PHASE23_CATALOG_FOREGROUND_INVENTORY",
]
