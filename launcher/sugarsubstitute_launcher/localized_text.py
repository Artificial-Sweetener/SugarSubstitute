#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Render fixed installer copy through one stable Qt translation context."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication

_CONTEXT = "LauncherMainWindow"


def launcher_text(source_text: str, *arguments: object) -> str:
    """Translate fixed copy and substitute ordered `%1`-style arguments."""

    translated = QCoreApplication.translate(_CONTEXT, source_text)
    for index, argument in enumerate(arguments, start=1):
        translated = translated.replace(f"%{index}", str(argument))
    return translated


__all__ = ["launcher_text"]
