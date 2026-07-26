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
    PromptAutocompleteAcceptanceController,
    PromptAutocompleteAcceptanceOutcome,
    PromptAutocompleteAcceptanceStatus,
)
from .autocomplete_acceptance_lifecycle import PromptAutocompleteAcceptanceLifecycle
from .autocomplete_controller import (
    PromptAutocompleteInputAdapter,
    PromptAutocompleteInputPort,
)
from .autocomplete_session import (
    PromptAutocompleteSessionController,
    selected_autocomplete_suggestion,
    selected_lora_autocomplete_candidate,
)
from .autocomplete_session_publication import PromptAutocompleteSessionPublication
from .autocomplete_timing import (
    PromptAutocompleteDismissReason,
    PromptAutocompleteLifecycleRequester,
    PromptAutocompleteRefreshTimer,
    PromptAutocompleteSourceSnapshot,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
)
from .controller import PromptInteractionEditor
from ..commands.context_insertion import (
    PromptCommandContextInsertState,
    PromptCommandCursor,
    PromptContextMenuTextInsertionExecutor,
    PromptTriggerWordInsertionExecutor,
)
from .clipboard_history_controller import (
    PromptClipboardHistoryActions,
    PromptClipboardHistoryController,
    PromptClipboardHistoryCursorSink,
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
    PromptKeymapWeightPort,
    PromptSurfaceKeyHandler,
    PromptSurfaceKeyHost,
)
from .mouse_selection_controller import (
    PromptMouseSelectionController,
    PromptMouseSelectionHost,
    PromptMouseSelectionWeightPort,
    PromptSurfaceMouseHandler,
    PromptSurfaceMouseHost,
    prompt_word_bounds,
)
from .prompt_menu_presenter import (
    PromptContextMenuPreparationPort,
    PromptContextMenuRequestPresenter,
    PromptContextMenuSnapshotReader,
    PromptMenuEditorHost,
    PromptSegmentPresetHostAdapter,
)
from .reorder_interaction import (
    PromptReorderInteractionEditor,
    PromptReorderInteractionHost,
    PromptReorderInteractionOwner,
)
from .reorder_overlay_session import (
    PromptReorderOverlaySessionEditor,
    PromptReorderOverlaySessionHost,
    PromptReorderOverlaySessionOwner,
)
from .reorder_commit_execution import (
    PromptReorderCommandResultPort,
    PromptReorderCommandSurface,
    PromptReorderCommitExecution,
    PromptReorderCommitExecutor,
)
from .reorder_cursor_selection import PromptReorderCursor
from .reorder_overlay_port import PromptReorderOverlayFactory, PromptReorderOverlayPort
from .trigger_word_action_adapter import PromptTriggerWordActionAdapter
from .wheel_controller import (
    PromptSurfaceWheelHandler,
    PromptSurfaceWheelHost,
    PromptTokenWeightWheelIntentController,
    PromptWheelController,
    PromptWheelScrollResult,
)
from .weight_interaction import PromptWeightInteraction

__all__ = [
    "PromptAutocompleteAcceptanceController",
    "PromptAutocompleteAcceptanceLifecycle",
    "PromptAutocompleteAcceptanceOutcome",
    "PromptAutocompleteAcceptanceStatus",
    "PromptAutocompleteInputAdapter",
    "PromptAutocompleteInputPort",
    "PromptAutocompleteDismissReason",
    "PromptAutocompleteLifecycleRequester",
    "PromptAutocompleteRefreshTimer",
    "PromptAutocompleteSessionController",
    "PromptAutocompleteSessionPublication",
    "PromptAutocompleteSourceSnapshot",
    "PromptAutocompleteSourceSnapshotController",
    "PromptAutocompleteTimingController",
    "PromptClipboardHistoryActions",
    "PromptClipboardHistoryController",
    "PromptClipboardHistoryCursorSink",
    "PromptCommandContextInsertState",
    "PromptCommandCursor",
    "PromptContextMenuTextInsertionExecutor",
    "PromptTriggerWordInsertionExecutor",
    "PromptContextMenuRequestPresenter",
    "PromptContextMenuPreparationPort",
    "PromptContextMenuSnapshotReader",
    "PromptDanbooruDialogFactory",
    "PromptDanbooruDialogHostAdapter",
    "PromptDanbooruPasteScheduler",
    "PromptDanbooruDialogRunner",
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
    "PromptInteractionEditor",
    "PromptInteractionController",
    "PromptLoraPickerActivationSignal",
    "PromptLoraPickerDataSource",
    "PromptLoraPickerPopupFactory",
    "PromptLoraPickerPopupPresenter",
    "PromptLoraPickerPopupView",
    "PromptSemanticRefreshPort",
    "PromptKeymapController",
    "PromptKeymapHost",
    "PromptKeymapWeightPort",
    "PromptMenuEditorHost",
    "PromptMouseSelectionController",
    "PromptMouseSelectionHost",
    "PromptMouseSelectionWeightPort",
    "PromptReorderCursor",
    "PromptReorderCommandResultPort",
    "PromptReorderCommandSurface",
    "PromptReorderCommitExecution",
    "PromptReorderCommitExecutor",
    "PromptReorderInteractionEditor",
    "PromptReorderInteractionHost",
    "PromptReorderInteractionOwner",
    "PromptReorderOverlayFactory",
    "PromptReorderOverlayPort",
    "PromptReorderOverlaySessionEditor",
    "PromptReorderOverlaySessionHost",
    "PromptReorderOverlaySessionOwner",
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
    "PromptWeightInteraction",
    "PromptWheelScrollResult",
    "is_emphasis_weight_action",
    "is_weight_syntax_action",
    "prompt_word_bounds",
    "selected_autocomplete_suggestion",
    "selected_lora_autocomplete_candidate",
]
