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

"""Prompt editor benchmark method instrumentation."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from types import MethodType
from typing import cast

from substitute.application.prompt_editor import PromptDocumentService
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.features.context_menu_actions import (
    PromptContextMenuActionController,
)
from substitute.presentation.editor.prompt_editor.features.danbooru_actions import (
    PromptDanbooruActionController,
)
from substitute.presentation.editor.prompt_editor.features.diagnostics_controller import (
    PromptDiagnosticsFeatureController,
)
from substitute.presentation.editor.prompt_editor.features.lora_metadata_controller import (
    PromptLoraMetadataFeatureController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_controller import (
    PromptSegmentPresetController,
)
from substitute.presentation.editor.prompt_editor.features.scene_controller import (
    PromptSceneFeatureController,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_controller import (
    PromptAutocompleteCoordinator,
)
from substitute.presentation.editor.prompt_editor.interactions.mouse_selection_controller import (
    PromptSurfaceMouseHandler,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewScheduler,
)
from substitute.presentation.editor.prompt_editor.overlays.autocomplete_panel import (
    PromptAutocompletePanel,
)
from substitute.presentation.editor.prompt_editor.overlays.autocomplete_presenter import (
    PromptAutocompletePanelPresenter,
)
from substitute.presentation.editor.prompt_editor.projection.autocomplete_ghost_text import (
    PromptAutocompleteGhostTextPublisher,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_editor import (
    PromptProjectionPlainTextApplyStatus,
)
from substitute.presentation.editor.prompt_editor.projection.line_layout import (
    PromptProjectionLineLayoutBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.shell import (
    context_menu_controller as prompt_context_menu_module,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    PromptShellContextMenuController,
)
from substitute.presentation.editor.prompt_editor.shell.fill_plane import (
    PromptFillPlane,
)
from substitute.presentation.editor.prompt_editor.shell.qfluent_chrome import (
    PromptShellQFluentChrome,
)
from substitute.presentation.editor.prompt_editor.shell.scroll_delegate import (
    PromptShellScrollDelegate,
)


class InstrumentedMethods:
    """Patch selected prompt editor methods for local measurement."""

    def __init__(self, instrumentation: Instrumentation) -> None:
        """Store target counters and original methods."""

        self._instrumentation = instrumentation
        self._originals: list[tuple[type[object], str, object]] = []

    def __enter__(self) -> InstrumentedMethods:
        """Install method wrappers."""

        self._patch(
            PromptProjectionSurface,
            "_rebuild_projection",
            self._instrumentation.projection_rebuild,
        )
        self._patch(
            PromptProjectionSurface,
            "paintEvent",
            self._instrumentation.surface_paint_event,
        )
        self._patch(
            PromptProjectionSurface,
            "refresh_geometry",
            self._instrumentation.surface_refresh_geometry,
        )
        self._patch(
            PromptProjectionSurface,
            "refresh_scroll",
            self._instrumentation.surface_refresh_scroll,
        )
        self._patch(
            PromptProjectionSurface,
            "resizeEvent",
            self._instrumentation.surface_resize_event,
        )
        self._patch(
            PromptProjectionSurface,
            "_sync_layout_state",
            self._instrumentation.surface_sync_layout,
        )
        self._patch(
            PromptProjectionSurface,
            "_apply_source_replacement_source_change",
            self._instrumentation.surface_source_apply,
        )
        self._patch(
            PromptEditingSession,
            "replace_source_range",
            self._instrumentation.editing_replace_range,
        )
        self._patch(
            PromptEditingSession,
            "replace_full_source",
            self._instrumentation.editing_replace_full_source,
        )
        self._patch(
            PromptEditingSession,
            "set_cursor_positions",
            self._instrumentation.editing_set_cursor_positions,
        )
        self._patch(
            PromptEditingSession,
            "selection",
            self._instrumentation.editing_selection,
        )
        self._patch(
            PromptEditingSession,
            "paste",
            self._instrumentation.editing_paste,
        )
        self._patch(
            PromptProjectionLineLayoutBuilder,
            "build_snapshot",
            self._instrumentation.layout_snapshot,
        )
        self._patch(
            PromptAutocompleteCoordinator,
            "refresh_for_query",
            self._instrumentation.autocomplete_refresh,
        )
        self._patch(
            PromptDocumentService,
            "autocomplete_query_at_cursor",
            self._instrumentation.autocomplete_query_resolution,
        )
        self._patch(
            PromptDocumentService,
            "lora_autocomplete_query_at_cursor",
            self._instrumentation.autocomplete_query_resolution,
        )
        self._patch(
            PromptDocumentService,
            "wildcard_autocomplete_query_at_cursor",
            self._instrumentation.autocomplete_query_resolution,
        )
        self._patch(
            PromptDocumentService,
            "scene_autocomplete_query_at_cursor",
            self._instrumentation.autocomplete_query_resolution,
        )
        self._patch(
            PromptAutocompletePanelPresenter,
            "present_session",
            self._instrumentation.autocomplete_panel_update,
        )
        self._patch(
            PromptAutocompletePanel,
            "_set_lora_wall_state",
            self._instrumentation.autocomplete_lora_wall_update,
        )
        self._patch(
            PromptAutocompleteGhostTextPublisher,
            "publish_for_session",
            self._instrumentation.autocomplete_preview_update,
        )
        self._patch(
            PromptDiagnosticsFeatureController,
            "activate",
            self._instrumentation.diagnostics_activation,
        )
        self._patch(
            PromptDiagnosticsFeatureController,
            "refresh_visible_diagnostics",
            self._instrumentation.diagnostics_visible_refresh,
        )
        self._patch(
            PromptDiagnosticsFeatureController,
            "actions_for_diagnostic",
            self._instrumentation.diagnostics_action_prepare,
        )
        self._patch(
            PromptContextMenuActionController,
            "snapshot_for_menu",
            self._instrumentation.context_menu_snapshot,
        )
        self._patch(
            PromptSceneFeatureController,
            "position_context",
            self._instrumentation.context_menu_scene_context,
        )
        self._patch(
            PromptLoraMetadataFeatureController,
            "trigger_word_actions_for_prompt",
            self._instrumentation.context_menu_lora_actions,
        )
        self._patch(
            PromptSegmentPresetController,
            "menu_snapshot",
            self._instrumentation.context_menu_segment_snapshot,
        )
        self._patch(
            PromptDanbooruActionController,
            "snapshot_for_selection",
            self._instrumentation.context_menu_danbooru_snapshot,
        )
        self._patch(
            PromptShellContextMenuController,
            "show_prompt_context_menu",
            self._instrumentation.context_menu_open,
        )
        self._patch(
            PromptReorderPreviewScheduler,
            "request",
            self._instrumentation.reorder_preview_request,
        )
        self._patch(
            PromptReorderPreviewScheduler,
            "_run",
            self._instrumentation.reorder_preview_run,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_try_apply_fast_trailing_plain_insert_projection",
            self._instrumentation.projection_fast_insert_applied,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_try_apply_fast_trailing_plain_delete_projection",
            self._instrumentation.projection_fast_delete_applied,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_try_apply_fast_trailing_newline_insert_projection",
            self._instrumentation.projection_fast_newline_applied,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_try_apply_fast_trailing_newline_delete_projection",
            self._instrumentation.projection_fast_newline_applied,
        )
        self._patch_incremental_projection_result()
        self._patch_bool_result(
            PromptProjectionSurface,
            "_defer_wrap_reflow_projection_update",
            self._instrumentation.projection_wrap_deferred,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_try_defer_immediate_projection_fallback_update",
            self._instrumentation.projection_fallback_deferred,
        )
        self._patch_projection_paint_result()
        self._patch(
            PromptProjectionSurface,
            "_diagnostic_fragments_for_paint",
            self._instrumentation.diagnostic_fragment_lookup,
        )
        self._patch(
            PromptProjectionSurface,
            "_preserve_diagnostic_fragment_cache_for_incremental_edit",
            self._instrumentation.diagnostic_cache_preserve,
        )
        self._patch(
            PromptProjectionSurface,
            "_clear_diagnostic_fragment_cache",
            self._instrumentation.diagnostic_cache_clear,
        )
        self._patch_bool_result(
            PromptProjectionSurface,
            "_fill_band_cache_matches",
            self._instrumentation.fill_band_cache_hit,
            false_counter=self._instrumentation.fill_band_cache_miss,
        )
        self._patch(
            PromptShellScrollDelegate,
            "handle_viewport_scroll_value_changed",
            self._instrumentation.shell_scroll_event,
        )
        self._patch(
            PromptShellScrollDelegate,
            "sync_shell_geometry",
            self._instrumentation.shell_geometry_sync,
        )
        self._patch(
            PromptShellScrollDelegate,
            "layout_surface",
            self._instrumentation.shell_layout_surface,
        )
        self._patch(
            PromptFillPlane,
            "paintEvent",
            self._instrumentation.fill_plane_paint,
        )
        self._patch(
            PromptSurfaceMouseHandler,
            "update_hovered_token",
            self._instrumentation.hover_update,
        )
        self._patch(
            PromptSurfaceMouseHandler,
            "handle_viewport_mouse_move",
            self._instrumentation.hover_move,
        )
        self._patch(
            PromptShellQFluentChrome,
            "handle_focus_in",
            self._instrumentation.focus_in,
        )
        self._patch(
            cast(type[object], prompt_context_menu_module._PromptEditorTextEditMenu),
            "exec",
            OperationCounter(),
            replacement=lambda _instance, *_args, **_kwargs: None,
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Restore original methods."""

        _ = (exc_type, exc, tb)
        for owner, name, original in reversed(self._originals):
            setattr(owner, name, original)

    def _patch(
        self,
        owner: type[object],
        name: str,
        counter: OperationCounter,
        *,
        replacement: Callable[..., object] | None = None,
    ) -> None:
        """Patch one method and record its elapsed time."""

        original = getattr(owner, name, None)
        if original is None:
            return
        self._originals.append((owner, name, original))

        def wrapper(instance: object, *args: object, **kwargs: object) -> object:
            started_at = perf_counter()
            try:
                if replacement is not None:
                    return replacement(instance, *args, **kwargs)
                bound = MethodType(cast(Callable[..., object], original), instance)
                return bound(*args, **kwargs)
            finally:
                counter.record((perf_counter() - started_at) * 1000.0)

        setattr(owner, name, wrapper)

    def _patch_bool_result(
        self,
        owner: type[object],
        name: str,
        true_counter: OperationCounter,
        *,
        false_counter: OperationCounter | None = None,
    ) -> None:
        """Patch one bool-returning method and record the chosen branch."""

        original = getattr(owner, name, None)
        if original is None:
            return
        self._originals.append((owner, name, original))

        def wrapper(instance: object, *args: object, **kwargs: object) -> object:
            started_at = perf_counter()
            result = MethodType(cast(Callable[..., object], original), instance)(
                *args,
                **kwargs,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            if result is True:
                true_counter.record(elapsed_ms)
            elif false_counter is not None:
                false_counter.record(elapsed_ms)
            return result

        setattr(owner, name, wrapper)

    def _patch_incremental_projection_result(self) -> None:
        """Patch middle plain-text projection edits by apply status."""

        name = "_try_apply_incremental_plain_text_projection"
        original = getattr(PromptProjectionSurface, name, None)
        if original is None:
            return
        self._originals.append((PromptProjectionSurface, name, original))

        def wrapper(instance: object, *args: object, **kwargs: object) -> object:
            started_at = perf_counter()
            result = MethodType(cast(Callable[..., object], original), instance)(
                *args,
                **kwargs,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            if result is PromptProjectionPlainTextApplyStatus.APPLIED:
                self._instrumentation.projection_incremental_applied.record(elapsed_ms)
            elif result is PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW:
                self._instrumentation.projection_incremental_deferred.record(elapsed_ms)
            else:
                self._instrumentation.projection_incremental_rejected.record(elapsed_ms)
            return result

        setattr(PromptProjectionSurface, name, wrapper)

    def _patch_projection_paint_result(self) -> None:
        """Patch projection content paint cache outcomes by result category."""

        name = "_paint_projection_content"
        original = getattr(PromptProjectionSurface, name, None)
        if original is None:
            return
        self._originals.append((PromptProjectionSurface, name, original))

        def wrapper(instance: object, *args: object, **kwargs: object) -> object:
            started_at = perf_counter()
            result = MethodType(cast(Callable[..., object], original), instance)(
                *args,
                **kwargs,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            if result == "hit":
                self._instrumentation.paint_cache_hit.record(elapsed_ms)
            elif result in {"miss", "bypass_small_cache_miss"}:
                self._instrumentation.paint_cache_miss.record(elapsed_ms)
            else:
                self._instrumentation.paint_cache_bypass.record(elapsed_ms)
            return result

        setattr(PromptProjectionSurface, name, wrapper)
