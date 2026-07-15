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

"""Expose prompt-editor interaction controller boundaries."""

from __future__ import annotations

from .autocomplete_acceptance import (
    PromptAutocompleteAcceptanceCommandFactory,
    PromptAutocompleteAcceptanceController,
    PromptAutocompleteAcceptanceEditor,
    PromptAutocompleteAcceptanceOutcome,
    PromptAutocompleteAcceptanceStatus,
)
from .autocomplete_controller import (
    PromptAutocompleteCoordinator,
    PromptAutocompleteController,
    PromptAutocompleteCursor,
    PromptAutocompleteEditor,
    PromptAutocompleteQueryEditor,
    PromptAutocompleteQueryRefreshController,
)
from .autocomplete_session import (
    PromptAutocompleteSessionController,
    selected_autocomplete_suggestion,
    selected_lora_autocomplete_candidate,
)
from .autocomplete_timing import (
    PromptAutocompleteDismissReason,
    PromptAutocompleteLifecycleRequester,
    PromptAutocompleteRefreshTimer,
    PromptAutocompleteSourceEditor,
    PromptAutocompleteSourceSnapshot,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
    PromptAutocompleteTimingCursor,
)
from .command_adapter import (
    PromptCommandContextInsertState,
    PromptCommandCursor,
    PromptCommandExecutionPort,
    PromptContextMenuTextInsertionExecutor,
    PromptTriggerWordInsertionExecutor,
    PromptEditorCommandAdapter,
)
from .clipboard_history_controller import (
    PromptClipboardHistoryActions,
    PromptClipboardHistoryController,
    PromptClipboardHistorySink,
    PromptClipboardSourceReplacementExecutor,
    PromptDanbooruPasteScheduler,
    PromptTextClipboard,
)
from .danbooru_dialog_runner import (
    PromptDanbooruDialogFactory,
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
)
from .controller import (
    PromptInteractionController,
    PromptSemanticRefreshPort,
)
from .edit_command_router import PromptEditCommandRouter
from .emphasis_controller import (
    PromptEmphasisController,
    PromptEmphasisHost,
    PromptEmphasisSyntaxAction,
    is_emphasis_weight_action,
)
from .exact_weight_controller import (
    PromptExactWeightController,
    PromptExactWeightHost,
    PromptExactWeightProjectionHost,
    is_weight_syntax_action,
)
from .external_url_action_runner import (
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpener,
    PromptExternalUrlOpenRequest,
)
from .inline_lora_menu_presenter import (
    PromptInlineLoraContextMenuPresenter,
    PromptInlineLoraMetadataActions,
    PromptInlineLoraTriggerWordActions,
    PromptInlineLoraShellMenu,
)
from .lora_picker_presenter import (
    PromptLoraPickerActivationSignal,
    PromptLoraPickerDataSource,
    PromptLoraPickerPopupFactory,
    PromptLoraPickerPopupPresenter,
    PromptLoraPickerPopupView,
)
from .keymap import (
    PromptKeymapController,
    PromptKeymapHost,
    PromptSurfaceKeyHandler,
    PromptSurfaceKeyHost,
)
from .mouse_selection_controller import (
    PromptMouseSelectionController,
    PromptMouseSelectionHost,
    PromptSurfaceMouseHandler,
    PromptSurfaceMouseHost,
    prompt_word_bounds,
)
from .prompt_menu_presenter import (
    PromptContextMenuRequestPresenter,
    PromptMenuEditorHost,
    PromptSegmentPresetHostAdapter,
)
from .reorder_controller import (
    PromptReorderController,
    PromptReorderCursor,
    PromptReorderEditorHost,
    PromptReorderHost,
    PromptReorderOverlayFactory,
    PromptReorderOverlayPort,
)
from .reorder_preview_sync import (
    PromptReorderPreviewScheduler,
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncController,
    PromptReorderPreviewSyncState,
)
from .reorder_session import PromptReorderSessionController
from .trigger_word_action_adapter import PromptTriggerWordActionAdapter
from .wheel_controller import (
    PromptSurfaceWheelHandler,
    PromptSurfaceWheelHost,
    PromptTokenWeightWheelIntentController,
    PromptWheelController,
    PromptWheelHost,
    PromptWheelScrollResult,
)

__all__ = [
    "PromptAutocompleteAcceptanceCommandFactory",
    "PromptAutocompleteAcceptanceController",
    "PromptAutocompleteAcceptanceEditor",
    "PromptAutocompleteAcceptanceOutcome",
    "PromptAutocompleteAcceptanceStatus",
    "PromptAutocompleteCoordinator",
    "PromptAutocompleteController",
    "PromptAutocompleteCursor",
    "PromptAutocompleteDismissReason",
    "PromptAutocompleteEditor",
    "PromptAutocompleteQueryEditor",
    "PromptAutocompleteQueryRefreshController",
    "PromptAutocompleteLifecycleRequester",
    "PromptAutocompleteRefreshTimer",
    "PromptAutocompleteSessionController",
    "PromptAutocompleteSourceEditor",
    "PromptAutocompleteSourceSnapshot",
    "PromptAutocompleteSourceSnapshotController",
    "PromptAutocompleteTimingController",
    "PromptAutocompleteTimingCursor",
    "PromptClipboardHistoryActions",
    "PromptClipboardHistoryController",
    "PromptClipboardHistorySink",
    "PromptClipboardSourceReplacementExecutor",
    "PromptCommandContextInsertState",
    "PromptCommandCursor",
    "PromptCommandExecutionPort",
    "PromptContextMenuTextInsertionExecutor",
    "PromptTriggerWordInsertionExecutor",
    "PromptContextMenuRequestPresenter",
    "PromptDanbooruDialogFactory",
    "PromptDanbooruDialogHostAdapter",
    "PromptDanbooruPasteScheduler",
    "PromptDanbooruDialogRunner",
    "PromptEditorCommandAdapter",
    "PromptEditCommandRouter",
    "PromptEmphasisController",
    "PromptEmphasisHost",
    "PromptEmphasisSyntaxAction",
    "PromptExactWeightController",
    "PromptExactWeightHost",
    "PromptExactWeightProjectionHost",
    "PromptExternalUrlActionRunner",
    "PromptExternalUrlOpener",
    "PromptExternalUrlOpenRequest",
    "PromptInlineLoraContextMenuPresenter",
    "PromptInlineLoraMetadataActions",
    "PromptInlineLoraTriggerWordActions",
    "PromptInlineLoraShellMenu",
    "PromptInteractionController",
    "PromptLoraPickerActivationSignal",
    "PromptLoraPickerDataSource",
    "PromptLoraPickerPopupFactory",
    "PromptLoraPickerPopupPresenter",
    "PromptLoraPickerPopupView",
    "PromptSemanticRefreshPort",
    "PromptKeymapController",
    "PromptKeymapHost",
    "PromptMenuEditorHost",
    "PromptMouseSelectionController",
    "PromptMouseSelectionHost",
    "PromptReorderController",
    "PromptReorderCursor",
    "PromptReorderEditorHost",
    "PromptReorderHost",
    "PromptReorderOverlayFactory",
    "PromptReorderOverlayPort",
    "PromptReorderPreviewScheduler",
    "PromptReorderPreviewSyncContext",
    "PromptReorderPreviewSyncController",
    "PromptReorderPreviewSyncState",
    "PromptReorderSessionController",
    "PromptSegmentPresetHostAdapter",
    "PromptSurfaceKeyHandler",
    "PromptSurfaceKeyHost",
    "PromptSurfaceMouseHandler",
    "PromptSurfaceMouseHost",
    "PromptSurfaceWheelHandler",
    "PromptSurfaceWheelHost",
    "PromptTokenWeightWheelIntentController",
    "PromptTextClipboard",
    "PromptTriggerWordActionAdapter",
    "PromptWheelController",
    "PromptWheelHost",
    "PromptWheelScrollResult",
    "is_emphasis_weight_action",
    "is_weight_syntax_action",
    "prompt_word_bounds",
    "selected_autocomplete_suggestion",
    "selected_lora_autocomplete_candidate",
]
