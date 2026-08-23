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

"""Contracts for prompt-editor LoRA metadata refresh lifecycle."""

from __future__ import annotations


from typing import Any, cast

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)

from .refresh_support import (
    _ImmediateDispatcher,
    _LoraMetadataInteractionControllerDouble,
    _PromptEditorLoraMetadataRefreshDouble,
    _import_prompt_editor_module,
)
from .support import (
    _LoraMetadataHost,
    _QueuedDispatcher,
    _metadata_owners,
    _raw_midna_item,
)


def test_refresh_lora_metadata_keeps_dirty_flag_when_picker_refresh_fails() -> None:
    """Picker refresh failures do not block render metadata refresh."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        picker_error=RuntimeError("picker failed")
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_refresh.dirty is False


def test_refresh_lora_metadata_keeps_dirty_flag_when_projection_queue_fails() -> None:
    """Projection queue failures leave visible LoRA metadata retryable."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        interaction_controller=_LoraMetadataInteractionControllerDouble(
            schedule_error=RuntimeError("queue failed")
        )
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_refresh.dirty is True


def test_refresh_lora_metadata_keeps_dirty_flag_when_projection_not_queued() -> None:
    """A failed projection queue attempt does not consume dirty metadata."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble(
        interaction_controller=_LoraMetadataInteractionControllerDouble(
            schedule_result=False
        )
    )

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_refresh.dirty is True


def test_refresh_lora_metadata_clears_dirty_flag_after_successful_queue() -> None:
    """A successfully queued metadata refresh consumes the dirty flag."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble()

    refreshed = mod.PromptEditor.refresh_lora_metadata_if_visible(editor)

    assert refreshed is True
    assert editor._lora_metadata_refresh.dirty is False
    assert editor._lora_thumbnail_cache.clear_calls == 0


def test_catalog_update_lora_metadata_refresh_preserves_thumbnail_cache() -> None:
    """Catalog metadata refresh does not drop existing LoRA thumbnail pixmaps."""

    mod = _import_prompt_editor_module()
    editor = _PromptEditorLoraMetadataRefreshDouble()

    refreshed = mod.PromptEditor._refresh_lora_render_metadata_after_catalog_update(
        editor
    )

    assert refreshed is True
    assert editor._lora_metadata_refresh.dirty is False
    assert editor._lora_thumbnail_cache.clear_calls == 0


def test_picker_refresh_updates_inline_lora_render_metadata() -> None:
    """A direct picker catalog refresh also refreshes visible LoRA chips."""

    class _PickerRefreshCatalog:
        """Expose a revision-changing LoRA picker refresh."""

        def __init__(self) -> None:
            """Initialize catalog rows and revision accounting."""

            self.cache_revision = 0

        def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
            """Return a LoRA row and advance the catalog revision."""

            self.cache_revision += 1
            return (_raw_midna_item(),)

        def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
            """Return no passive rows because this test exercises refresh."""

            return ()

        def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
            """Return no cached rows before the explicit refresh."""

            return None

    editor = _PromptEditorLoraMetadataRefreshDouble()
    owners = _metadata_owners(
        host=cast(_LoraMetadataHost, editor),
        lora_catalog=cast(Any, _PickerRefreshCatalog()),
        dispatcher=cast(_QueuedDispatcher, _ImmediateDispatcher()),
    )
    editor._lora_metadata_presentation = owners.presentation
    editor._lora_metadata_refresh = owners.refresh

    result = editor._lora_metadata_refresh.refresh_lora_picker_snapshot_now(
        reason="test",
    )

    assert [item.prompt_name for item in result.snapshot.items] == [
        r"illustrious\characters\raw_midna"
    ]
    assert editor._interaction_controller.schedule_calls == 1


def test_lora_metadata_controller_coalesces_pending_render_refreshes() -> None:
    """Repeated metadata requests schedule one feature-controller refresh."""

    dispatcher = _QueuedDispatcher()
    editor = _PromptEditorLoraMetadataRefreshDouble()
    owners = _metadata_owners(
        host=cast(_LoraMetadataHost, editor),
        lora_catalog=None,
        dispatcher=dispatcher,
    )
    editor._lora_metadata_presentation = owners.presentation
    controller = owners.refresh

    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert len(dispatcher.callbacks) == 1

    dispatcher.callbacks.pop()()

    assert editor._interaction_controller.schedule_calls == 1


def test_lora_metadata_controller_coalesces_render_refresh() -> None:
    """Render refresh scheduling should be owned and coalesced by the feature."""

    dispatcher = _QueuedDispatcher()
    host = _LoraMetadataHost()
    controller = _metadata_owners(host=host, dispatcher=dispatcher).refresh

    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert controller.schedule_render_metadata_refresh(reason="lora_metadata") is True
    assert len(dispatcher.callbacks) == 1

    dispatcher.callbacks.pop()()

    assert host.refresh_calls == 1
    assert controller.dirty is False
