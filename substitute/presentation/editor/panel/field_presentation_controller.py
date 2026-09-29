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

"""Present field-owned metadata, thumbnails, and progress in an editor panel."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtWidgets import QWidget

from substitute.application.model_metadata import ModelMetadataRefreshEvent
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

from .field_registry import EditorFieldRegistry
from .widgets.fields.load_mask import MaskPicker

_LOGGER = get_logger("presentation.editor.panel.field_presentation_controller")


class PresetContextRefreshPort(Protocol):
    """Refresh preset context after model metadata changes."""

    def refresh(self, *, reason: str) -> None:
        """Refresh derived preset context for one named reason."""


class EditorPanelFieldPresentationController:
    """Own presentation updates for field widgets mounted in one editor panel."""

    def __init__(
        self,
        panel: QWidget,
        *,
        field_registry: EditorFieldRegistry,
        preset_context_refresh: PresetContextRefreshPort,
    ) -> None:
        """Bind the controller to the mounted field registry and panel surface."""

        self._panel = panel
        self._field_registry = field_registry
        self._preset_context_refresh = preset_context_refresh

    def refresh_mask_picker(
        self,
        cube_alias: str,
        node_name: str,
        new_path: str,
    ) -> None:
        """Refresh the mask picker matching one cube and node identity."""

        inspected_metadata: list[object] = []
        for picker in self._panel.findChildren(MaskPicker):
            metadata = picker.property("input_metadata")
            inspected_metadata.append(metadata)
            if not (
                isinstance(metadata, dict)
                and metadata.get("cube_alias") == cube_alias
                and metadata.get("node_name") == node_name
            ):
                continue
            refresh_mask_path = getattr(picker, "refresh_mask_path", None)
            if callable(refresh_mask_path):
                refresh_mask_path(new_path)
            else:
                picker.set_mask_path(new_path)
            log_debug(
                _LOGGER,
                "Refreshed mask picker thumbnail",
                cube_alias=cube_alias,
                node_name=node_name,
                replacement_path_present=bool(new_path),
                refresh_method=(
                    "refresh_mask_path"
                    if callable(refresh_mask_path)
                    else "set_mask_path"
                ),
            )
            return
        log_warning(
            _LOGGER,
            "Failed to refresh mask picker because no matching picker was found",
            cube_alias=cube_alias,
            node_name=node_name,
            replacement_path_present=bool(new_path),
            inspected_count=len(inspected_metadata),
        )

    def refresh_model_metadata(self) -> None:
        """Refresh every model picker from current metadata."""

        for entry in self._field_registry.entries():
            if isinstance(entry.widget, ModelPickerField):
                entry.widget.refresh_metadata()
        self._preset_context_refresh.refresh(reason="model_metadata_refreshed")

    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Refresh model pickers affected by one metadata event."""

        refreshed_count = 0
        for entry in self._field_registry.entries():
            if isinstance(
                entry.widget, ModelPickerField
            ) and entry.widget.refresh_metadata_for_event(event):
                refreshed_count += 1
        self._preset_context_refresh.refresh(reason="model_metadata_event_refreshed")
        return refreshed_count

    def clear_model_thumbnail_caches_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Clear model picker thumbnail caches affected by one asset event."""

        cleared_count = 0
        for entry in self._field_registry.entries():
            if isinstance(
                entry.widget, ModelPickerField
            ) and entry.widget.clear_thumbnail_cache_for_event(event):
                cleared_count += 1
        return cleared_count

    def clear_lora_thumbnail_caches(self) -> int:
        """Clear LoRA thumbnail caches owned by mounted prompt editors."""

        cleared_count = 0
        for prompt_editor in self._panel.findChildren(PromptEditor):
            clear_thumbnail_cache = getattr(
                prompt_editor,
                "clear_lora_thumbnail_cache",
                None,
            )
            if not callable(clear_thumbnail_cache):
                continue
            clear_thumbnail_cache()
            cleared_count += 1
        return cleared_count

    def set_model_field_load_progress(
        self,
        *,
        cube_alias: str,
        node_name: str,
        field_key: str,
        percent: float | None,
        active: bool,
    ) -> None:
        """Route source-enriched model-load progress to one model picker field."""

        widget = self._field_registry.widget_map.get((cube_alias, node_name, field_key))
        if widget is None:
            log_info(
                _LOGGER,
                "Model-load progress target widget was not found",
                cube_alias=cube_alias,
                node_name=node_name,
                field_key=field_key,
                percent=percent,
                active=active,
            )
            return
        if not isinstance(widget, ModelPickerField):
            log_info(
                _LOGGER,
                "Model-load progress target widget is not a model picker",
                cube_alias=cube_alias,
                node_name=node_name,
                field_key=field_key,
                widget_type=type(widget).__name__,
                percent=percent,
                active=active,
            )
            return
        log_info(
            _LOGGER,
            "Applied model-load progress to model picker",
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            percent=percent,
            active=active,
        )
        widget.set_model_load_progress(percent=percent, active=active)

    def clear_model_field_load_progress(self) -> None:
        """Clear model-load progress from every unique model picker."""

        seen: set[int] = set()
        for widget in self._field_registry.widget_map.values():
            widget_id = id(widget)
            if widget_id in seen:
                continue
            seen.add(widget_id)
            if isinstance(widget, ModelPickerField):
                widget.set_model_load_progress(percent=None, active=False)


__all__ = ["EditorPanelFieldPresentationController", "PresetContextRefreshPort"]
