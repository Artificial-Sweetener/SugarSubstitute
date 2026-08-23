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

"""Prompt-editor refresh doubles for LoRA metadata lifecycle tests."""

from __future__ import annotations


import importlib
from typing import Any, cast

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)

from .support import (
    _ImmediateDispatcher,
    _LoraMetadataHost,
    _QueuedDispatcher,
    _metadata_owners,
)

__all__ = [
    "_ImmediateDispatcher",
    "_LoraMetadataInteractionControllerDouble",
    "_PromptEditorLoraMetadataRefreshDouble",
    "_import_prompt_editor_module",
]


class _LoraMetadataInteractionControllerDouble:
    """Expose LoRA metadata refresh seams consumed by PromptEditor."""

    def __init__(
        self,
        *,
        has_lora_spans: bool = True,
        schedule_result: bool = True,
        schedule_error: Exception | None = None,
    ) -> None:
        """Store deterministic LoRA refresh behavior."""

        self._has_lora_spans = has_lora_spans
        self._schedule_result = schedule_result
        self._schedule_error = schedule_error
        self.schedule_calls = 0

    def has_lora_spans(self) -> bool:
        """Return whether the prompt currently contains LoRA spans."""

        return self._has_lora_spans

    def refresh_lora_render_metadata(self, *, reason: str) -> bool:
        """Record and return the configured metadata refresh result."""

        assert reason == "lora_metadata"
        self.schedule_calls += 1
        if self._schedule_error is not None:
            raise self._schedule_error
        return self._schedule_result


class _FailingLoraPickerCatalog:
    """Raise when picker rows are refreshed."""

    cache_revision = 0

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail one active picker refresh."""

        raise RuntimeError("picker failed")

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Fail one passive picker load."""

        raise RuntimeError("picker failed")

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached rows before explicit refresh."""

        return None


class _LoraThumbnailCacheDouble:
    """Expose thumbnail-cache behavior consumed by PromptEditor refresh tests."""

    def __init__(self, *, clear_error: Exception | None = None) -> None:
        """Store deterministic cache clear behavior."""

        self._clear_error = clear_error
        self.clear_calls = 0

    def clear(self) -> None:
        """Record and optionally fail a cache clear request."""

        self.clear_calls += 1
        if self._clear_error is not None:
            raise self._clear_error


class _PromptEditorLoraMetadataRefreshDouble:
    """Provide the PromptEditor attributes needed by metadata refresh tests."""

    def __init__(
        self,
        *,
        dirty: bool = True,
        visible: bool = True,
        picker_error: Exception | None = None,
        interaction_controller: _LoraMetadataInteractionControllerDouble | None = None,
        thumbnail_cache: _LoraThumbnailCacheDouble | None = None,
    ) -> None:
        """Store deterministic prompt-editor metadata refresh collaborators."""

        self._visible = visible
        self._interaction_controller = (
            interaction_controller or _LoraMetadataInteractionControllerDouble()
        )
        self._lora_thumbnail_cache = thumbnail_cache or _LoraThumbnailCacheDouble()
        owners = _metadata_owners(
            host=cast(_LoraMetadataHost, self),
            lora_catalog=(
                cast(Any, _FailingLoraPickerCatalog()) if picker_error else None
            ),
            dispatcher=cast(_QueuedDispatcher, _ImmediateDispatcher()),
        )
        self._lora_metadata_presentation = owners.presentation
        self._lora_metadata_refresh = owners.refresh
        if dirty:
            self._lora_metadata_refresh.mark_dirty()

    def isVisible(self) -> bool:  # noqa: N802
        """Return whether the fake editor is visible."""

        return self._visible

    def toPlainText(self) -> str:  # noqa: N802
        """Return empty source text for metadata-controller tests."""

        return ""

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for metadata-controller tests."""

        return None

    def has_lora_spans_for_metadata(self) -> bool:
        """Return whether the fake editor currently has LoRA spans."""

        return self._interaction_controller.has_lora_spans()

    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool:
        """Delegate render metadata refresh to the interaction double."""

        return self._interaction_controller.refresh_lora_render_metadata(reason=reason)


def _import_prompt_editor_module() -> Any:
    """Import the prompt editor widget module."""

    return importlib.import_module(
        "substitute.presentation.editor.prompt_editor.widget"
    )
