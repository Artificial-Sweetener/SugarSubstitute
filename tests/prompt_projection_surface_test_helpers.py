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

"""Shared helpers for prompt projection surface tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
    PromptSourceNormalizationService,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.ports import PromptWildcardResolution
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE, ThumbnailAsset
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptEditController,
)
from substitute.presentation.editor.prompt_editor.editing_session.undo_coalescing import (
    PromptUndoCoalescingController,
)
from substitute.presentation.editor.prompt_editor.interactions.edit_command_router import (
    PromptEditCommandRouter,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
    PromptProjectionUndoPayload,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionToken,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientInsertionOverlay,
)
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    surface_for,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile


@pytest.fixture(name="widgets")
def projection_surface_widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one projection-surface test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


class ManualUndoCoalescingTimer:
    """Provide deterministic timer hooks for directly composed surface tests."""

    def __init__(self) -> None:
        """Create an idle manual timer."""

        self._handler: Callable[[], None] | None = None

    def set_timeout_handler(self, handler: Callable[[], None]) -> None:
        """Store the callback that a test may trigger manually."""

        self._handler = handler

    def start(self) -> None:
        """Record timer start without scheduling real time."""

    def stop(self) -> None:
        """Record timer stop without scheduling real time."""


@dataclass(frozen=True, slots=True)
class SurfaceEditBlockActions:
    """Adapt an edit controller to the surface viewport action protocol."""

    edit_controller: PromptEditController[PromptProjectionUndoPayload]

    def begin_surface_edit_block(self, *, finish_typing: bool = True) -> None:
        """Begin a grouped edit block through the edit controller."""

        self.edit_controller.begin_edit_block(finish_typing=finish_typing)

    def end_surface_edit_block(self) -> None:
        """End a grouped edit block through the edit controller."""

        self.edit_controller.end_edit_block()

    def finish_surface_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush pending key edit groups through the edit controller."""

        self.edit_controller.finish_pending_key_edit_block(reason=reason)


class NoopClipboardHistoryActions:
    """Satisfy key handler clipboard shortcuts for directly composed surfaces."""

    def copy(self) -> None:
        """Ignore copy in bare-surface tests."""

    def cut(self) -> None:
        """Ignore cut in bare-surface tests."""

    def paste(self) -> None:
        """Ignore paste in bare-surface tests."""

    def select_all(self) -> None:
        """Ignore select-all in bare-surface tests."""

    def undo(self) -> None:
        """Ignore undo in bare-surface tests."""

    def redo(self) -> None:
        """Ignore redo in bare-surface tests."""


def new_projection_surface(
    parent: QWidget | None = None,
    *,
    lora_thumbnail_cache: PromptLoraThumbnailCache | None = None,
) -> PromptProjectionSurface:
    """Create a surface with composition-owned mutation collaborators."""

    session = PromptEditingSession[PromptProjectionUndoPayload](
        source_text="",
        source_revision=0,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=100,
        max_redo_states=100,
    )
    surface = PromptProjectionSurface(
        parent,
        editing_session=session,
        lora_thumbnail_cache=lora_thumbnail_cache,
    )
    edit_controller = PromptEditController[PromptProjectionUndoPayload](
        session=session,
        undo_payload_provider=surface,
        availability_signal_sink=surface,
        projection_mutation_sink=surface,
    )
    router = PromptEditCommandRouter[PromptProjectionUndoPayload](
        edit_controller=edit_controller,
        normalizer=PromptSourceNormalizationService(),
        mutation_sink=surface,
        source_text_provider=surface.toPlainText,
        cursor_position_provider=lambda: surface.cursor_position,
        anchor_position_provider=lambda: surface.anchor_position,
        exact_source_provider=surface.exact_source_editing_enabled,
    )
    coalescing = PromptUndoCoalescingController[PromptProjectionUndoPayload](
        edit_controller=edit_controller,
        typing_timer=ManualUndoCoalescingTimer(),
        delete_timer=ManualUndoCoalescingTimer(),
        cursor_position=lambda: surface.cursor_position,
        selection_empty=lambda: not surface.textCursor().hasSelection(),
    )
    edit_controller.set_pending_key_flusher(coalescing)
    surface.attach_runtime_mutation_actions(
        source_mutation_actions=router,
        edit_block_actions=SurfaceEditBlockActions(edit_controller),
        clipboard_history_actions=NoopClipboardHistoryActions(),
        undo_coalescing_actions=coalescing,
    )
    cast(Any, surface)._phase21_test_edit_command_router = router
    cast(Any, surface)._phase21_test_edit_controller = edit_controller
    return surface


def surface_router(
    surface: PromptProjectionSurface,
) -> PromptEditCommandRouter[PromptProjectionUndoPayload]:
    """Return the composed command router for one bare-surface test."""

    test_router = getattr(surface, "_phase21_test_edit_command_router", None)
    if test_router is not None:
        return cast(PromptEditCommandRouter[PromptProjectionUndoPayload], test_router)
    parent = surface.parentWidget()
    while parent is not None:
        if isinstance(parent, PromptEditor):
            return cast(
                PromptEditCommandRouter[PromptProjectionUndoPayload],
                cast(Any, parent)._command_adapter._executor,  # noqa: SLF001
            )
        parent = parent.parentWidget()
    return cast(
        PromptEditCommandRouter[PromptProjectionUndoPayload],
        cast(Any, surface)._phase21_test_edit_command_router,
    )


def surface_edit_controller(
    surface: PromptProjectionSurface,
) -> PromptEditController[PromptProjectionUndoPayload]:
    """Return the composed edit controller for one bare-surface test."""

    test_controller = getattr(surface, "_phase21_test_edit_controller", None)
    if test_controller is not None:
        return cast(PromptEditController[PromptProjectionUndoPayload], test_controller)
    parent = surface.parentWidget()
    while parent is not None:
        if isinstance(parent, PromptEditor):
            return cast(
                PromptEditController[PromptProjectionUndoPayload],
                cast(Any, parent)._edit_controller,  # noqa: SLF001
            )
        parent = parent.parentWidget()
    return cast(
        PromptEditController[PromptProjectionUndoPayload],
        cast(Any, surface)._phase21_test_edit_controller,
    )


def first_emphasis_token(box: PromptEditor) -> PromptProjectionToken:
    """Return the first collapsed emphasis token from one live projection."""

    return next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )


class PositionEvent:
    """Expose a viewport-local position for tooltip provider tests."""

    def __init__(self, position: QPointF) -> None:
        """Store the event position."""

        self._position = position

    def position(self) -> QPointF:
        """Return the stored viewport-local position."""

        return QPointF(self._position)


class StaticPromptLoraCatalog:
    """Return deterministic LoRA catalog rows for projection tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store configured LoRA rows."""

        self._items = items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows."""

        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured LoRA rows without simulating backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the configured LoRA row matching one prompt name."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None


class RecordingThumbnailAssetRepository:
    """Record thumbnail asset reads without returning decoded image data."""

    def __init__(self) -> None:
        """Initialize the storage-key read log."""

        self.reads: list[str] = []

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record one requested storage key and return no asset."""

        self.reads.append(storage_key)
        return None


def lora_catalog_item_with_banner(
    *,
    prompt_name: str = "midna",
    storage_key: str = "midna:banner:768x160",
) -> PromptLoraCatalogItem:
    """Return one LoRA catalog item with a banner thumbnail variant."""

    return PromptLoraCatalogItem(
        display_name="Midna",
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder="",
        basename=prompt_name,
        extension=".safetensors",
        thumbnail_variants=(
            PromptLoraThumbnailVariant(
                size=768,
                storage_key=storage_key,
                width=768,
                height=160,
                content_format="png",
                byte_size=1024,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=prompt_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=prompt_name.casefold(),
    )


def install_lora_wildcard_prompt_state(
    surface: PromptProjectionSurface,
    text: str,
) -> None:
    """Install a resolved prompt state containing LoRA and wildcard decorations."""

    wildcard_gateway = StaticPromptWildcardCatalogGateway(
        {
            ("animal", "simple", None): PromptWildcardResolution(
                identifier="animal",
                wildcard_form="simple",
                exists=True,
            ),
        }
    )
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    render_plan = PromptSyntaxService(
        wildcard_gateway,
        prompt_lora_catalog_service=StaticPromptLoraCatalog(
            (lora_catalog_item_with_banner(),)
        ),
    ).build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    surface_router(surface).set_source_text(text)
    surface.set_prompt_state(document_view, render_plan)
    surface.flush_pending_projection_update(reason="test")


def projection_token_kinds(
    surface: PromptProjectionSurface,
) -> tuple[PromptProjectionTokenKind, ...]:
    """Return the projected token kind sequence for one surface."""

    return tuple(token.kind for token in surface.projection_document().tokens)


def apply_source_range_to_projection(
    surface: PromptProjectionSurface,
    next_text: str,
    *,
    cursor_position: int,
    anchor_position: int,
    emit_text_changed: bool,
    rebuild_immediately: bool = True,
    optimistic_prompt_state: tuple[
        PromptDocumentView,
        PromptSyntaxRenderPlan,
    ]
    | None = None,
    source_edit_start: int,
    source_edit_end: int,
    source_edit_replacement_text: str,
    previous_source_text: str,
) -> None:
    """Apply a source transaction through the Phase 2.6 editing-session path."""

    source_change = surface._editing_session.replace_source_range(  # noqa: SLF001
        start=source_edit_start,
        end=source_edit_end,
        replacement_text=source_edit_replacement_text,
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=False,
        undo_snapshot=surface_router(surface).current_undo_snapshot(),
    )
    assert source_change.next_snapshot.source_text == next_text
    surface._source_change_applier._apply_editing_session_source_change(  # noqa: SLF001
        source_change,
        emit_text_changed=emit_text_changed,
        rebuild_immediately=rebuild_immediately,
        optimistic_prompt_state=optimistic_prompt_state,
        source_edit_start=source_edit_start,
        source_edit_end=source_edit_end,
        source_edit_replacement_text=source_edit_replacement_text,
        previous_source_text=previous_source_text,
    )


def valid_transient_insertion_overlay(
    surface: PromptProjectionSurface,
) -> PromptProjectionTransientInsertionOverlay | None:
    """Return controller-owned transient insertion overlay state for assertions."""

    return surface._transient_edit_overlays.valid_insertion_overlay(  # noqa: SLF001
        freshness_is_stale_safe=surface.has_stale_projection_geometry(),
        source_revision=surface._source_revision,  # noqa: SLF001
    )


def render_surface_viewport(surface: PromptProjectionSurface) -> QImage:
    """Render one projection surface viewport into an offscreen image."""

    image = QImage(
        max(1, surface.viewport().width()),
        max(1, surface.viewport().height()),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(0)
    painter = QPainter(image)
    try:
        surface.viewport().render(painter, QPoint(0, 0))
    finally:
        painter.end()
    return image


def delay_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Make projection scheduling observable without sleeping in tests."""

    scheduler = surface._projection_freshness_controller.update_scheduler  # noqa: SLF001
    scheduler._fixed_interval_ms = 60_000  # noqa: SLF001
    scheduler._interval_ms = 60_000  # noqa: SLF001
    scheduler._timer.setInterval(60_000)  # noqa: SLF001


def flush_projection_update_scheduler(surface: PromptProjectionSurface) -> None:
    """Apply a delayed scheduled projection update through the production scheduler."""

    surface._projection_freshness_controller.update_scheduler.flush_now(reason="test")  # noqa: SLF001


def flush_semantic_refresh(box: PromptEditor) -> None:
    """Apply queued semantic prompt state without waiting for Qt timers."""

    cast(Any, box)._interaction_controller.flush_pending_semantic_refresh(  # noqa: SLF001
        reason="test"
    )
