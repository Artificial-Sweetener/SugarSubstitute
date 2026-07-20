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

"""Describe application-owned copy without depending on a GUI framework."""

from __future__ import annotations

from typing import TypeAlias


class ApplicationMessage(str):
    """Carry one English source and opaque interpolation arguments through layers."""

    source_text: str
    arguments: tuple[object, ...]

    def __new__(
        cls,
        source_text: str,
        arguments: tuple[object, ...] = (),
    ) -> ApplicationMessage:
        """Create a string-compatible marker whose stored value is its source."""

        instance = super().__new__(cls, source_text)
        instance.source_text = source_text
        instance.arguments = arguments
        return instance


ApplicationText: TypeAlias = str | ApplicationMessage


def app_text(source_text: str, *arguments: object) -> ApplicationMessage:
    """Mark SugarSubstitute-owned English copy for presentation translation."""

    return ApplicationMessage(source_text, arguments)


def opaque_text(text: str) -> str:
    """Classify exact authored, persisted, protocol, or technical text as opaque."""

    return text


def render_source_application_text(text: ApplicationText) -> str:
    """Render application-owned copy in English without a GUI dependency."""

    if not isinstance(text, ApplicationMessage):
        return text
    rendered = text.source_text
    for index in range(len(text.arguments), 0, -1):
        argument = text.arguments[index - 1]
        replacement = (
            render_source_application_text(argument)
            if isinstance(argument, ApplicationMessage)
            else str(argument)
        )
        rendered = rendered.replace(f"%{index}", replacement)
    return rendered


__all__ = [
    "ApplicationMessage",
    "ApplicationText",
    "app_text",
    "opaque_text",
    "render_source_application_text",
]
