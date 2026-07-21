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

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any

from PySide6.QtCore import QMargins, QPointF, QSize, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from .projection.reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from .projection.reorder_surface_chrome import PromptReorderSurfaceChromeChip

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptMutationService,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    PromptSyntaxSpanView,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.prompt_editor import PromptSyntaxProfile
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.application.ports import PromptAutocompleteGateway
from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)

from .autocomplete_preview_state import PromptAutocompletePreviewState
from .composition import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorTaskExecutorFactory,
)
from .commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceIdentity,
    PromptCommandTextReplacement,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
)
from .overlays import (
    PromptAutocompletePanel,
    PromptTokenWeightControls,
)
from .features import (
    PromptContextMenuActionController,
    PromptDiagnosticsFeatureController,
    PromptFeatureProfileController,
)
from .interactions import PromptReorderOverlayPort, PromptWheelScrollResult
from .projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionToken,
    PromptWeightControlIdentity,
)
from .projection.selection_geometry import PromptProjectionSourceLineRect
from .projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from .projection.reorder_preview import PromptReorderPreviewState

class PromptEditor(QWidget):
    textChanged: Any
    cursorPositionChanged: Any
    undoAvailableChanged: Any
    redoAvailableChanged: Any
    resized: Any
    manualScrollHeightChanged: Any
    richPromptRenderingEnabledChanged: Any
    sceneQueueRequested: Any
    scrollDelegate: Any
    _surface: Any
    _feature_profile_controller: PromptFeatureProfileController
    _diagnostics_feature_controller: PromptDiagnosticsFeatureController
    _context_menu_action_controller: PromptContextMenuActionController
    _syntax_profile: PromptSyntaxProfile

    def __init__(
        self,
        parent: Any = ...,
        *,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        prompt_document_semantics: PromptDocumentSemantics | None = ...,
        danbooru_url_import_service: DanbooruUrlImportService | None = ...,
        danbooru_wiki_service: DanbooruWikiContentService | None = ...,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = ...,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = ...,
        prompt_feature_profile: PromptEditorFeatureProfile | None = ...,
        prompt_syntax_profile: PromptSyntaxProfile | None = ...,
        maximum_visible_lines: int | None = ...,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = ...,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = ...,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = ...,
        scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
        | None = ...,
        prompt_segment_preset_source: PromptSegmentPresetSource | None = ...,
        prompt_spellcheck_service: PromptSpellcheckService | None = ...,
        open_url: Callable[[str], bool] | None = ...,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = ...,
        prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = ...,
        danbooru_lookup_dispatcher_factory: (
            DanbooruWikiLookupDispatcherFactory | None
        ) = ...,
    ) -> None: ...
    @property
    def _autocomplete_panel(self) -> PromptAutocompletePanel | None: ...
    @property
    def _segment_overlay(self) -> PromptReorderOverlayPort | None: ...
    @property
    def _token_weight_control_overlay(self) -> PromptTokenWeightControls: ...
    def viewport(self) -> QWidget: ...
    def viewportMargins(self) -> QMargins: ...
    def setViewportMargins(
        self, left: int, top: int, right: int, bottom: int
    ) -> None: ...
    def verticalScrollBar(self) -> Any: ...
    def document(self) -> Any: ...
    def lineHeight(self) -> int: ...
    def minimumEditorHeight(self) -> int: ...
    def manualScrollHeight(self) -> int | None: ...
    def setManualScrollHeight(self, height: int | None) -> None: ...
    def sizeHint(self) -> QSize: ...
    def minimumSizeHint(self) -> QSize: ...
    def setPlaceholderText(self, text: str) -> None: ...
    def placeholderText(self) -> str: ...
    def setReadOnly(self, read_only: bool) -> None: ...
    def setFocus(
        self,
        reason: Qt.FocusReason = ...,
    ) -> None: ...
    def hasFocus(self) -> bool: ...
    def toPlainText(self) -> str: ...
    def setPlainText(self, text: str) -> None: ...
    def setSourceText(self, text: str) -> None: ...
    def replaceBaselineText(self, text: str) -> None: ...
    def replaceBaselineSourceText(self, text: str) -> None: ...
    def replaceBaselineSourceDocument(
        self,
        text: str,
        document_semantics: PromptDocumentSemantics,
    ) -> None: ...
    def preloadVisibleLoraBanners(
        self,
        *,
        on_complete: Callable[[], None],
    ) -> bool: ...
    def canUndo(self) -> bool: ...
    def canRedo(self) -> bool: ...
    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]: ...
    def current_source_line_index(self) -> int: ...
    def set_source_line_chrome_enabled(self, enabled: bool) -> None: ...
    def set_source_line_content_left_inset(self, inset: float) -> None: ...
    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None: ...
    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None: ...
    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None: ...
    def textCursor(self) -> Any: ...
    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity: ...
    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]: ...
    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]: ...
    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]: ...
    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]: ...
    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[object]: ...
    def setTextCursor(self, cursor: Any) -> None: ...
    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None: ...
    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = ...,
    ) -> None: ...
    def clear_emphasis_adjustment_session(self) -> None: ...
    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None: ...
    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None: ...
    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool: ...
    def prompt_weight_wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity: ...
    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = ...,
    ) -> None: ...
    def clear_transient_neutral_emphasis(self) -> None: ...
    def clear_overlay_owned_transient_neutral_emphasis(self) -> None: ...
    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None: ...
    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None: ...
    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool: ...
    def cursorRect(self) -> Any: ...
    def has_pending_projection_update(self) -> bool: ...
    def flush_pending_projection_update(self, *, reason: str) -> None: ...
    def commit_lora_autocomplete_replacement(self) -> None: ...
    def set_autocomplete_preview_state(
        self, preview_state: PromptAutocompletePreviewState | None
    ) -> None: ...
    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        active_index: int | None,
        *,
        query_identity: Hashable | None = ...,
    ) -> None: ...
    def clear_search_matches(self) -> None: ...
    def mark_lora_metadata_dirty(self) -> None: ...
    def refresh_lora_metadata_if_visible(self) -> bool: ...
    def refresh_prompt_segment_presets(self, *, reason: str) -> None: ...
    def displayMode(self) -> PromptProjectionDisplayMode: ...
    def setDisplayMode(self, display_mode: PromptProjectionDisplayMode) -> None: ...
    def richPromptRenderingEnabled(self) -> bool: ...
    def setRichPromptRenderingEnabled(self, enabled: bool) -> None: ...
    def cursorForPosition(self, position: Any) -> Any: ...
    def source_range_fragments(self, *, start: int, end: int) -> Any: ...
    def set_reorder_preview_state(
        self, preview_state: PromptReorderPreviewState | None
    ) -> None: ...
    def clear_reorder_preview_state(self) -> None: ...
    def set_wheel_intent_token_handlers(
        self,
        *,
        token_pointer_moved: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_wheel_ready: Callable[[PromptProjectionToken, QPointF], bool] | None,
        token_wheel_allowed: Callable[[PromptProjectionToken, QWheelEvent], bool]
        | None,
        token_wheel_activated: Callable[[PromptProjectionToken, QPointF], None] | None,
    ) -> None: ...
    def reorder_preview_fragments(self, *, start: int, end: int) -> Any: ...
    def reorder_live_chip_geometry_snapshot(
        self,
        *,
        layout_view: Any,
        chip_rendered_ranges_by_index: Any,
        chip_owned_ranges_by_index: Any,
    ) -> Any: ...
    def reorder_live_placement_snapshot(
        self,
        *,
        layout_view: Any,
        chip_geometry_snapshot: Any,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> Any: ...
    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: Any,
        layout_view: Any,
    ) -> Any: ...
    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: Any,
        chip_owned_ranges_by_index: Any,
    ) -> Any: ...
    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: Any,
        chip_owned_ranges_by_index: Any,
        chip_indices: frozenset[int] | None = ...,
    ) -> Any: ...
    def set_reorder_overlay_suppression_snapshots(
        self,
        snapshots_by_index: dict[int, PromptReorderProjectionPaintSnapshot],
    ) -> None: ...
    def set_reorder_surface_chrome(
        self,
        *,
        mode: str,
        chips: tuple[PromptReorderSurfaceChromeChip, ...],
    ) -> None: ...
    def reorder_preview_cursor_rect(self, position: int) -> Any: ...
    def reorder_base_drag_fragments(self, *, start: int, end: int) -> Any: ...
    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: Any,
        layout_view: Any,
    ) -> Any: ...
    def reorder_base_drag_cursor_rect(self, position: int) -> Any: ...
    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot: Any,
        layout_view: Any,
    ) -> Any: ...
    def reset_reorder_geometry_cache_counters(self) -> None: ...
    def reorder_geometry_cache_counters(self) -> dict[str, object]: ...
    def reorder_placement_at_rect(
        self,
        drag_rect: Any,
        *,
        snapshot: Any,
        active_placement_id: Any,
    ) -> Any: ...
    def active_syntax_span(self) -> PromptSyntaxSpanView | None: ...
    def replace_document_text(self, text: str) -> None: ...
    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None: ...
    def copy(self) -> None: ...
    def selectAll(self) -> None: ...
    def cut(self) -> None: ...
    def paste(self) -> None: ...
    def undo(self) -> None: ...
    def redo(self) -> None: ...
    def modify_emphasis(self, delta: float) -> None: ...
    def prompt_surface_handle_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult: ...
    def prompt_surface_wheel_event_is_allowed(self, event: QWheelEvent) -> bool: ...
    def forward_wheel_event_to_editor_panel(self, event: QWheelEvent) -> None: ...
    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool: ...
    def has_lora_spans_for_metadata(self) -> bool: ...
