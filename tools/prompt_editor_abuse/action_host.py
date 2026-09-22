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

"""Compose generic prompt-editor abuse action capabilities."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from .action_checkpoint import capture_action_checkpoint
from .event_loop_driver import PromptAbuseEventLoopDriver
from .feature_action_driver import PromptAbuseFeatureActionDriver
from .keyboard_action_driver import PromptAbuseKeyboardActionDriver
from .models import PromptAbuseAction
from .source_action_driver import PromptAbuseSourceActionDriver
from .weight_action_driver import PromptWeightActionDriver


class PromptAbuseActionHost:
    """Compose generic action owners and overridable container capabilities."""

    def __init__(self) -> None:
        """Create capability-owned collaborators for generic prompt actions."""

        self._event_loop = PromptAbuseEventLoopDriver()
        self._keyboard_actions = PromptAbuseKeyboardActionDriver()
        self._source_actions = PromptAbuseSourceActionDriver()
        self._feature_actions = PromptAbuseFeatureActionDriver(
            source_actions=self._source_actions
        )
        self._weight_actions = PromptWeightActionDriver()

    @property
    def event_loop(self) -> PromptAbuseEventLoopDriver:
        """Return the owner of bounded event-loop draining."""

        return self._event_loop

    @property
    def keyboard_actions(self) -> PromptAbuseKeyboardActionDriver:
        """Return the owner of named Qt keyboard actions."""

        return self._keyboard_actions

    @property
    def source_actions(self) -> PromptAbuseSourceActionDriver:
        """Return the owner of exact source cursor and pointer actions."""

        return self._source_actions

    @property
    def feature_actions(self) -> PromptAbuseFeatureActionDriver:
        """Return the owner of diagnostic, picker, and context-menu actions."""

        return self._feature_actions

    @property
    def weight_actions(self) -> PromptWeightActionDriver:
        """Return the owner of weighted-token pointer interactions."""

        return self._weight_actions

    def scroll_editor(self, editor: object, target: str) -> None:
        """Move the scrollbar; explicit event-turn actions measure publication."""

        scrollbar = cast(Any, editor).verticalScrollBar()
        if target == "top":
            value = scrollbar.minimum()
        elif target == "middle":
            value = (scrollbar.minimum() + scrollbar.maximum()) // 2
        elif target == "bottom":
            value = scrollbar.maximum()
        else:
            raise ValueError(f"Unsupported prompt abuse scroll target {target!r}.")
        scrollbar.setValue(value)

    def focus_cycle(self, target: QWidget) -> None:
        """Move focus away and back without creating another window."""

        target.clearFocus()
        self._event_loop.process_events(cycles=2)
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        self._event_loop.process_events(cycles=2)

    def resize_editor(self, editor: object, width: int, height: int) -> None:
        """Resize through the editor's durable manual-height owner."""

        prompt_editor = cast(Any, editor)
        prompt_editor.setManualScrollHeight(height)
        prompt_editor.resize(width, height)

    def workflow_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch workflows and return one timing for each visible transition."""

        raise RuntimeError("Workflow round trips require the real-shell action host.")

    def canvas_round_trip(self) -> tuple[tuple[str, float], ...]:
        """Switch canvases and return one timing for each visible transition."""

        raise RuntimeError("Canvas round trips require the real-shell action host.")

    def reorder_drag_press(self, editor: object, value: str) -> None:
        """Press a reorder chip when the concrete host supports it."""

        del editor, value
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_threshold(self, editor: object) -> None:
        """Cross the platform drag threshold when the concrete host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_move(self, editor: object, value: str) -> None:
        """Move an active reorder chip drag when its host supports it."""

        del editor, value
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_sweep(self, editor: object) -> None:
        """Sweep every prepared destination when the concrete host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_release(self, editor: object) -> None:
        """Release an active reorder chip drag when its host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_autoscroll(self, editor: object) -> None:
        """Autoscroll an active reorder drag when its host supports it."""

        del editor
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def reorder_drag_cancel(self, editor: object, target: QWidget) -> None:
        """Cancel an active reorder drag when its host supports it."""

        del editor, target
        raise RuntimeError("Pointer reorder requires the reorder action host.")

    def set_display_mode(self, editor: object, mode: str) -> None:
        """Switch the production editor between projected and raw source modes."""

        cast(Any, editor).setRichPromptRenderingEnabled(mode == "rich")

    def set_search_highlights(self, editor: object, action: PromptAbuseAction) -> None:
        """Publish or clear search highlights through the production feature owner."""

        prompt_editor = cast(Any, editor)
        if action.value == "set":
            prompt_editor.set_search_matches(
                action.source_ranges,
                action.active_index,
                query_identity=(
                    "prompt-abuse",
                    action.source_ranges,
                    action.active_index,
                ),
            )
            return
        prompt_editor.clear_search_matches()

    def capture_feature_checkpoint(
        self,
        editor: object,
        action: PromptAbuseAction,
    ) -> tuple[bool, str | None]:
        """Combine editor-owner and feature-driver checkpoints."""

        exact, mismatch = capture_action_checkpoint(editor, action)
        mismatches = [item for item in (mismatch,) if item is not None]
        feature_mismatch = self._feature_actions.checkpoint_mismatch(action)
        if feature_mismatch is not None:
            mismatches.append(feature_mismatch)
        return exact and not mismatches, ";".join(mismatches) or None


__all__ = ["PromptAbuseActionHost"]
