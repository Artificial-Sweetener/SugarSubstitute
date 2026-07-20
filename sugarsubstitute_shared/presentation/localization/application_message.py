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

"""Apply Qt translation to explicitly marked application copy."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QObject

from sugarsubstitute_shared.localization import ApplicationMessage, ApplicationText
from sugarsubstitute_shared.presentation.localization.application_text import (
    clear_localized_property,
    set_localized_text,
    translate_application_message,
)


class ApplicationTextTarget(Protocol):
    """Describe a Qt-like target exposing a normal text setter."""

    def setText(self, text: str) -> None:
        """Set normal visible text."""


def apply_application_text(
    target: ApplicationTextTarget,
    text: ApplicationText,
) -> None:
    """Bind marked copy or pass an opaque string through unchanged."""

    if isinstance(text, ApplicationMessage):
        set_localized_text(
            cast(QObject, target),
            text.source_text,
            *text.arguments,
        )
        return
    target_object = cast(QObject, target)
    clear_localized_property(target_object, "text")
    target.setText(text)


def render_application_text(text: ApplicationText) -> str:
    """Resolve a marked message now or preserve opaque content verbatim."""

    if isinstance(text, ApplicationMessage):
        return translate_application_message(text.source_text, *text.arguments)
    return text


__all__ = [
    "ApplicationMessage",
    "ApplicationText",
    "ApplicationTextTarget",
    "apply_application_text",
    "render_application_text",
]
