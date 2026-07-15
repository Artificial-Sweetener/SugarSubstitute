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

"""Persist prompt parenthesis education state through application settings."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from substitute.application.ports.prompt_parenthesis_education_state import (
    PromptParenthesisEducationState,
)

_NESTED_PARENTHESIS_TIP_KEY = "prompt_editor/nested_parenthesis_tip_seen"


class QtPromptParenthesisEducationState(PromptParenthesisEducationState):
    """Store one-time education state in the configured application settings."""

    def __init__(self, settings: QSettings | None = None) -> None:
        """Use the application QSettings identity unless a test store is supplied."""

        self._settings = settings or QSettings()

    def has_seen_nested_parenthesis_tip(self) -> bool:
        """Return whether the nested-parenthesis teaching tip was shown."""

        return bool(self._settings.value(_NESTED_PARENTHESIS_TIP_KEY, False, bool))

    def mark_nested_parenthesis_tip_seen(self) -> None:
        """Persist that the nested-parenthesis teaching tip has been shown."""

        self._settings.setValue(_NESTED_PARENTHESIS_TIP_KEY, True)


__all__ = ["QtPromptParenthesisEducationState"]
