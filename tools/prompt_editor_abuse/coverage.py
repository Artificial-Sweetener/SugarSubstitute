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

"""Define and audit required prompt-editor abuse operation coverage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .models import PromptAbuseScenario


class PromptEditorOperation(StrEnum):
    """Name one independently correct and performant editor operation."""

    TYPE = "text.type"
    BACKSPACE = "text.backspace"
    DELETE = "text.delete"
    ENTER = "text.enter"
    PASTE = "clipboard.paste"
    COPY = "clipboard.copy"
    CUT = "clipboard.cut"
    SELECT_ALL = "selection.select_all"
    SELECTION_REPLACE = "selection.replace"
    MOUSE_CARET = "selection.mouse_caret"
    MOUSE_DRAG_SELECTION = "selection.mouse_drag"
    LEFT_RIGHT = "navigation.left_right"
    UP_DOWN = "navigation.up_down"
    HOME_END = "navigation.home_end"
    SHIFT_SELECTION = "navigation.shift_selection"
    UNDO_REDO = "history.undo_redo"
    LONG_HISTORY = "history.long_chain"
    FOCUS = "lifecycle.focus"
    SCROLL = "lifecycle.scroll"
    RESIZE = "lifecycle.resize"
    WORKFLOW_SWITCH = "lifecycle.workflow_switch"
    CANVAS_SWITCH = "lifecycle.canvas_switch"
    VIEWPORT_PAINT = "paint.viewport"
    CARET_PAINT = "paint.caret"
    SELECTION_PAINT = "paint.selection"
    RAW_RICH_TOGGLE = "display.raw_rich_toggle"
    WRAPPING = "layout.wrapping"
    SEARCH_HIGHLIGHTS = "overlay.search_highlights"
    AUTOCOMPLETE_QUERY = "autocomplete.query"
    AUTOCOMPLETE_NAVIGATE = "autocomplete.navigate"
    AUTOCOMPLETE_ACCEPT = "autocomplete.accept"
    AUTOCOMPLETE_DISMISS = "autocomplete.dismiss"
    AUTOCOMPLETE_GHOST = "autocomplete.ghost"
    EMPHASIS_SYNTAX = "emphasis.syntax"
    EMPHASIS_SHORTCUT = "emphasis.shortcut"
    EMPHASIS_WHEEL = "emphasis.wheel"
    LORA_SYNTAX = "lora.syntax"
    LORA_AUTOCOMPLETE = "lora.autocomplete"
    LORA_PICKER = "lora.picker"
    LORA_TRIGGER_WORDS = "lora.trigger_words"
    WILDCARD_SYNTAX = "wildcard.syntax"
    WILDCARD_AUTOCOMPLETE = "wildcard.autocomplete"
    SPELLCHECK_DIAGNOSTIC = "diagnostic.spellcheck"
    DUPLICATE_DIAGNOSTIC = "diagnostic.duplicate"
    DIAGNOSTIC_CONTEXT_MENU = "diagnostic.context_menu"
    DIAGNOSTIC_ACTION = "diagnostic.action"
    DANBOORU_IMPORT = "danbooru.import"
    DANBOORU_WIKI = "danbooru.wiki"
    SCENE_CREATE = "scene.create"
    SCENE_EDIT = "scene.edit"
    SCENE_DELETE = "scene.delete"
    SCENE_ENTER_BODY = "scene.enter_body"
    WILDCARD_TXT = "wildcard_document.txt"
    WILDCARD_CSV = "wildcard_document.csv"
    WILDCARD_ZEBRA = "wildcard_document.zebra"
    WILDCARD_SCENE_ERROR = "wildcard_document.scene_error"
    WILDCARD_SCENE_HELP = "wildcard_document.scene_help"
    WILDCARD_DUPLICATE_SCOPE = "wildcard_document.duplicate_scope"
    REORDER_ALT_ENTER_EXIT = "reorder.alt_enter_exit"
    REORDER_KEYBOARD = "reorder.keyboard"
    REORDER_POINTER_BEGIN = "reorder.pointer_begin"
    REORDER_POINTER_MOVE = "reorder.pointer_move"
    REORDER_POINTER_DROP = "reorder.pointer_drop"
    REORDER_POINTER_CANCEL = "reorder.pointer_cancel"
    REORDER_PREVIEW = "reorder.preview"
    REORDER_AUTOSCROLL = "reorder.autoscroll"
    REORDER_WHOLE_LINE = "reorder.whole_line_candidate"
    REORDER_CROSS_LINE = "reorder.cross_line_tag"


@dataclass(frozen=True, slots=True)
class PromptEditorCoverageSnapshot:
    """Report covered and missing required operations for one scenario matrix."""

    covered: tuple[str, ...]
    missing: tuple[str, ...]


_SCENARIO_OPERATIONS: Final[dict[str, frozenset[PromptEditorOperation]]] = {
    "empty-key-slam": frozenset({PromptEditorOperation.TYPE}),
    "long-decorated-start": frozenset(
        {PromptEditorOperation.TYPE, PromptEditorOperation.WRAPPING}
    ),
    "long-decorated-middle": frozenset(
        {PromptEditorOperation.TYPE, PromptEditorOperation.WRAPPING}
    ),
    "long-decorated-end": frozenset(
        {PromptEditorOperation.TYPE, PromptEditorOperation.WRAPPING}
    ),
    "mixed-destructive-editing": frozenset(
        {
            PromptEditorOperation.TYPE,
            PromptEditorOperation.BACKSPACE,
            PromptEditorOperation.DELETE,
            PromptEditorOperation.LEFT_RIGHT,
        }
    ),
    "paste-undo-redo": frozenset(
        {PromptEditorOperation.PASTE, PromptEditorOperation.UNDO_REDO}
    ),
    "scene-marker-creation": frozenset(
        {
            PromptEditorOperation.ENTER,
            PromptEditorOperation.SCENE_CREATE,
            PromptEditorOperation.SCENE_ENTER_BODY,
        }
    ),
    "scene-edit-delete-immediate": frozenset(
        {PromptEditorOperation.SCENE_EDIT, PromptEditorOperation.SCENE_DELETE}
    ),
    "scene-spaced-title-typing": frozenset(
        {
            PromptEditorOperation.TYPE,
            PromptEditorOperation.WRAPPING,
            PromptEditorOperation.SCENE_CREATE,
            PromptEditorOperation.SCENE_EDIT,
        }
    ),
    "scene-enter-backspace-relocation-torture": frozenset(
        {
            PromptEditorOperation.ENTER,
            PromptEditorOperation.BACKSPACE,
            PromptEditorOperation.MOUSE_CARET,
            PromptEditorOperation.SCENE_ENTER_BODY,
            PromptEditorOperation.VIEWPORT_PAINT,
        }
    ),
    "selection-replace-delete": frozenset(
        {PromptEditorOperation.SELECTION_REPLACE, PromptEditorOperation.DELETE}
    ),
    "resize-wrap-churn": frozenset(
        {PromptEditorOperation.RESIZE, PromptEditorOperation.WRAPPING}
    ),
    "autocomplete-race-churn": frozenset(
        {
            PromptEditorOperation.AUTOCOMPLETE_QUERY,
            PromptEditorOperation.AUTOCOMPLETE_DISMISS,
        }
    ),
    "autocomplete-navigation-acceptance": frozenset(
        {
            PromptEditorOperation.AUTOCOMPLETE_QUERY,
            PromptEditorOperation.AUTOCOMPLETE_NAVIGATE,
            PromptEditorOperation.AUTOCOMPLETE_ACCEPT,
            PromptEditorOperation.AUTOCOMPLETE_DISMISS,
            PromptEditorOperation.AUTOCOMPLETE_GHOST,
        }
    ),
    "lifecycle-scroll-switch-churn": frozenset(
        {
            PromptEditorOperation.FOCUS,
            PromptEditorOperation.SCROLL,
            PromptEditorOperation.WORKFLOW_SWITCH,
            PromptEditorOperation.CANVAS_SWITCH,
        }
    ),
    "long-decorated-pointer-reorder-visibility": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.VIEWPORT_PAINT,
            PromptEditorOperation.SCROLL,
            PromptEditorOperation.WRAPPING,
        }
    ),
    "long-wrapped-cross-line-pointer-reorder-visibility": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.REORDER_CROSS_LINE,
            PromptEditorOperation.VIEWPORT_PAINT,
            PromptEditorOperation.SCROLL,
            PromptEditorOperation.WRAPPING,
        }
    ),
    "max-span-pointer-reorder-preview-visibility": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.REORDER_CROSS_LINE,
            PromptEditorOperation.VIEWPORT_PAINT,
            PromptEditorOperation.WRAPPING,
        }
    ),
    "scene-partition-pointer-reorder-visibility": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.REORDER_CROSS_LINE,
            PromptEditorOperation.SCENE_EDIT,
            PromptEditorOperation.VIEWPORT_PAINT,
            PromptEditorOperation.WRAPPING,
        }
    ),
    "scene-marker-alt-release-retention": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.SCENE_EDIT,
            PromptEditorOperation.VIEWPORT_PAINT,
        }
    ),
    "prompt-viewport-repaint": frozenset({PromptEditorOperation.VIEWPORT_PAINT}),
    "prompt-long-decorated-repaint": frozenset(
        {PromptEditorOperation.VIEWPORT_PAINT, PromptEditorOperation.WRAPPING}
    ),
    "raw-rich-toggle-churn": frozenset({PromptEditorOperation.RAW_RICH_TOGGLE}),
    "search-highlight-scroll-paint": frozenset(
        {
            PromptEditorOperation.SEARCH_HIGHLIGHTS,
            PromptEditorOperation.VIEWPORT_PAINT,
            PromptEditorOperation.SCROLL,
        }
    ),
    "caret-selection-repaint": frozenset(
        {
            PromptEditorOperation.CARET_PAINT,
            PromptEditorOperation.SELECTION_PAINT,
        }
    ),
    "emphasis-syntax-formation": frozenset({PromptEditorOperation.EMPHASIS_SYNTAX}),
    "emphasis-keyboard-shortcut": frozenset({PromptEditorOperation.EMPHASIS_SHORTCUT}),
    "emphasis-pointer-wheel": frozenset({PromptEditorOperation.EMPHASIS_WHEEL}),
    "mouse-caret-drag-selection": frozenset(
        {
            PromptEditorOperation.MOUSE_CARET,
            PromptEditorOperation.MOUSE_DRAG_SELECTION,
            PromptEditorOperation.SELECTION_PAINT,
        }
    ),
    "wildcard-txt-zebra-typing": frozenset(
        {PromptEditorOperation.WILDCARD_TXT, PromptEditorOperation.WILDCARD_ZEBRA}
    ),
    "wildcard-csv-quoted-typing": frozenset({PromptEditorOperation.WILDCARD_CSV}),
    "wildcard-scene-marker-error": frozenset(
        {PromptEditorOperation.WILDCARD_SCENE_ERROR}
    ),
    "wildcard-prompt-syntax": frozenset({PromptEditorOperation.WILDCARD_SYNTAX}),
    "wildcard-duplicate-candidate-scope": frozenset(
        {
            PromptEditorOperation.WILDCARD_DUPLICATE_SCOPE,
            PromptEditorOperation.DUPLICATE_DIAGNOSTIC,
        }
    ),
    "wildcard-scene-context-help": frozenset(
        {
            PromptEditorOperation.WILDCARD_SCENE_ERROR,
            PromptEditorOperation.WILDCARD_SCENE_HELP,
            PromptEditorOperation.DIAGNOSTIC_CONTEXT_MENU,
        }
    ),
    "wildcard-alt-zebra-reorder": frozenset(
        {
            PromptEditorOperation.REORDER_ALT_ENTER_EXIT,
            PromptEditorOperation.REORDER_KEYBOARD,
            PromptEditorOperation.REORDER_CROSS_LINE,
            PromptEditorOperation.WILDCARD_ZEBRA,
        }
    ),
    "wildcard-mouse-drag-zebra": frozenset(
        {
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_DROP,
            PromptEditorOperation.REORDER_PREVIEW,
            PromptEditorOperation.WILDCARD_ZEBRA,
        }
    ),
    "wildcard-viewport-repaint": frozenset(
        {PromptEditorOperation.VIEWPORT_PAINT, PromptEditorOperation.WILDCARD_ZEBRA}
    ),
    "clipboard-navigation-selection": frozenset(
        {
            PromptEditorOperation.COPY,
            PromptEditorOperation.CUT,
            PromptEditorOperation.SELECT_ALL,
            PromptEditorOperation.UP_DOWN,
            PromptEditorOperation.HOME_END,
            PromptEditorOperation.SHIFT_SELECTION,
        }
    ),
    "long-undo-redo-history": frozenset(
        {PromptEditorOperation.UNDO_REDO, PromptEditorOperation.LONG_HISTORY}
    ),
    "spellcheck-diagnostic-action": frozenset(
        {
            PromptEditorOperation.SPELLCHECK_DIAGNOSTIC,
            PromptEditorOperation.DIAGNOSTIC_CONTEXT_MENU,
            PromptEditorOperation.DIAGNOSTIC_ACTION,
        }
    ),
    "danbooru-url-paste-import": frozenset({PromptEditorOperation.DANBOORU_IMPORT}),
    "danbooru-wiki-selection-menu": frozenset({PromptEditorOperation.DANBOORU_WIKI}),
    "lora-syntax-formation": frozenset({PromptEditorOperation.LORA_SYNTAX}),
    "lora-autocomplete-acceptance": frozenset(
        {
            PromptEditorOperation.LORA_AUTOCOMPLETE,
            PromptEditorOperation.AUTOCOMPLETE_QUERY,
            PromptEditorOperation.AUTOCOMPLETE_ACCEPT,
            PromptEditorOperation.AUTOCOMPLETE_GHOST,
        }
    ),
    "wildcard-autocomplete-acceptance": frozenset(
        {
            PromptEditorOperation.WILDCARD_AUTOCOMPLETE,
            PromptEditorOperation.AUTOCOMPLETE_QUERY,
            PromptEditorOperation.AUTOCOMPLETE_ACCEPT,
            PromptEditorOperation.AUTOCOMPLETE_GHOST,
        }
    ),
    "wildcard-whole-line-pointer-cancel": frozenset(
        {
            PromptEditorOperation.REORDER_WHOLE_LINE,
            PromptEditorOperation.REORDER_POINTER_BEGIN,
            PromptEditorOperation.REORDER_POINTER_CANCEL,
        }
    ),
    "wildcard-pointer-drag-autoscroll": frozenset(
        {
            PromptEditorOperation.REORDER_AUTOSCROLL,
            PromptEditorOperation.REORDER_POINTER_MOVE,
            PromptEditorOperation.REORDER_POINTER_CANCEL,
        }
    ),
    "lora-picker-open-activate": frozenset({PromptEditorOperation.LORA_PICKER}),
    "lora-trigger-word-menu-action": frozenset(
        {
            PromptEditorOperation.LORA_TRIGGER_WORDS,
            PromptEditorOperation.DIAGNOSTIC_CONTEXT_MENU,
        }
    ),
}


def capture_operation_coverage(
    scenarios: tuple[PromptAbuseScenario, ...],
) -> PromptEditorCoverageSnapshot:
    """Return honest required-operation coverage for supplied named scenarios."""

    covered_operations = frozenset(
        operation
        for scenario in scenarios
        for operation in _SCENARIO_OPERATIONS.get(scenario.name, frozenset())
    )
    required_operations = frozenset(PromptEditorOperation)
    return PromptEditorCoverageSnapshot(
        covered=tuple(sorted(operation.value for operation in covered_operations)),
        missing=tuple(
            sorted(
                operation.value
                for operation in required_operations - covered_operations
            )
        ),
    )


__all__ = [
    "PromptEditorCoverageSnapshot",
    "PromptEditorOperation",
    "capture_operation_coverage",
]
