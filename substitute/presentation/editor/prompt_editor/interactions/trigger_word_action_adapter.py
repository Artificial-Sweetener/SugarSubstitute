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

"""Adapt prepared LoRA trigger-word actions into Qt menu actions."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_tooltip,
)

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import QApplication, QWidget

from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from ..features import PromptLoraTriggerWordsAction
from .command_adapter import PromptTriggerWordInsertionExecutor

_TRIGGER_MENU_TEXT_WIDTH = 190
_TRIGGER_MENU_FULL_LABEL_PROPERTY = "promptFullTriggerWordsLabel"


class PromptTriggerWordActionAdapter:
    """Convert prepared trigger-word actions into Qt menu actions."""

    def __init__(
        self,
        *,
        action_parent: QWidget,
        text_insertion_executor: PromptTriggerWordInsertionExecutor,
        identity_validator: Callable[[PromptFeatureSnapshotIdentity], bool],
    ) -> None:
        """Store collaborators needed for QAction adaptation."""

        self._action_parent = action_parent
        self._text_insertion_executor = text_insertion_executor
        self._identity_validator = identity_validator

    def actions_for_trigger_words(
        self,
        prepared_actions: tuple[PromptLoraTriggerWordsAction, ...],
    ) -> tuple[QAction, ...]:
        """Convert prepared LoRA trigger-word actions into Qt menu actions."""

        return tuple(
            action
            for prepared_action in prepared_actions
            if (action := self.action_for_trigger_words(prepared_action)) is not None
        )

    def action_for_trigger_words(
        self,
        prepared_action: PromptLoraTriggerWordsAction | None,
    ) -> QAction | None:
        """Return a Qt action for one prepared trigger-word insertion."""

        if prepared_action is None or prepared_action.command_request is None:
            return None
        payload = prepared_action.command_request.payload
        full_label = payload.full_label
        action = QAction(
            self.trigger_words_action_label(payload.display_name),
            self._action_parent,
        )
        action.triggered.connect(lambda: self._execute_trigger_words(prepared_action))
        set_localized_tooltip(action, full_label.source_text, *full_label.arguments)
        action.setProperty(
            _TRIGGER_MENU_FULL_LABEL_PROPERTY,
            render_application_text(full_label),
        )
        return action

    def trigger_words_action_label(self, display_name: str) -> str:
        """Return a width-bounded LoRA display name for QAction rows."""

        metrics = QFontMetrics(QApplication.font())
        return metrics.elidedText(
            display_name,
            Qt.TextElideMode.ElideRight,
            _TRIGGER_MENU_TEXT_WIDTH,
        )

    def _execute_trigger_words(
        self,
        prepared_action: PromptLoraTriggerWordsAction,
    ) -> None:
        """Execute one prepared trigger action through identity validation."""

        command_request = prepared_action.command_request
        if command_request is None:
            return
        identity = command_request.identity
        if (
            identity.stale
            or identity.source_revision is None
            or not self._identity_validator(identity)
        ):
            return
        self._text_insertion_executor.execute_trigger_word_insertion(
            trigger_words=command_request.payload.insertion_text,
            source_identity=PromptCommandSourceIdentity(identity.source_revision),
        )


__all__ = [
    "PromptTriggerWordActionAdapter",
]
