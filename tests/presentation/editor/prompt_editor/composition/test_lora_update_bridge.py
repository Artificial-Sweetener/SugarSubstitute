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

"""Prove the mounted LoRA menu carries model updates into its popup."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.presentation.editor.prompt_editor.commands.context_insertion import (
    PromptContextInsertionService,
)
from substitute.presentation.editor.prompt_editor.composition.context import (
    PromptEditorCompositionContext,
)
from substitute.presentation.editor.prompt_editor.composition.menu_factory import (
    PromptEditorMenuFactory,
)
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
    PromptLoraMetadataPresentation,
    PromptLoraPickerSnapshot,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptExternalUrlActionRunner,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays.lora_wall import (
    PromptLoraPickerPopup,
)
from substitute.presentation.editor.prompt_editor.projection.undo_payload import (
    PromptProjectionUndoPayload,
)
from substitute.presentation.editor.prompt_editor.shell.fill_plane import (
    PromptFillPlaneHost,
)
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from tests.presentation.model_updates.support import update_proposal
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


class _LoraRows:
    """Offer one prepared LoRA row to the real menu composition."""

    def __init__(self, item: PromptLoraCatalogItem) -> None:
        """Retain the catalog row under test."""

        self._item = item

    @property
    def lora_picker_ready(self) -> bool:
        """Allow the menu to open its picker."""

        return True

    @property
    def lora_picker_snapshot(self) -> PromptLoraPickerSnapshot:
        """Return a warm snapshot with the exact model identity."""

        return PromptLoraPickerSnapshot(
            identity=CatalogSnapshotIdentity(),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            items=(self._item,),
            catalog_revision=1,
            dirty=False,
        )

    def schedule_text_for_lora(self, selected_lora: PromptLoraCatalogItem) -> str:
        """Return source text if the picker activates the row."""

        return f"<lora:{selected_lora.prompt_name}:1>"


def test_lora_menu_composition_shows_exact_model_update() -> None:
    """A configured update bridge must reach the actual popup tile."""

    ensure_qt_application()
    parent = QWidget()
    sha256 = "a" * 64
    item = PromptLoraCatalogItem(
        display_name="Mineru",
        display_subtitle=None,
        prompt_name="Mineru",
        backend_value="Mineru.safetensors",
        relative_path="Mineru.safetensors",
        folder="",
        basename="Mineru",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key="mineru",
        collision_count=1,
        has_collision=False,
        search_text="mineru",
        sha256=sha256,
    )
    updates = ModelUpdatePickerBridge(parent)
    context = PromptEditorCompositionContext(
        editor=parent,
        fill_plane_host=cast(PromptFillPlaneHost, parent),
        shell_viewport=parent,
        autocomplete_limit=10,
        autocomplete_minimum_prefix_length=1,
        fill_plane_factory=lambda *_args: QWidget(parent),
        resize_handle_factory=lambda _host: QWidget(parent),
    )
    presenter = PromptEditorMenuFactory(context).build_lora_picker_popup_presenter(
        lora_metadata=cast(PromptLoraMetadataPresentation, _LoraRows(item)),
        lora_thumbnail_cache=PromptLoraThumbnailCache(),
        context_insertion=cast(
            PromptContextInsertionService[PromptProjectionUndoPayload], object()
        ),
        last_context_menu_global_pos=lambda: None,
        cursor_global_position=lambda: QPoint(0, 0),
        external_url_actions=PromptExternalUrlActionRunner(lambda _url: False),
        model_updates=updates,
    )
    try:
        presenter.open_lora_picker()
        popup = parent.findChild(PromptLoraPickerPopup)
        assert popup is not None
        wall = popup._view
        assert wall.items()[0].corner_badge_icon is None

        updates.replace((update_proposal(sha256),))

        assert wall.items()[0].corner_badge_icon is not None
    finally:
        destroy_qt_object(parent)
