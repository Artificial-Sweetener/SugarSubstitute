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

"""Install optional Qt message tracing for targeted startup diagnostics."""

from __future__ import annotations

import os
import traceback

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("app.bootstrap.qt_message_trace")
QT_MESSAGE_TRACE_ENV = "SUGARSUBSTITUTE_TRACE_QT_MESSAGES"
FONT_WARNING_SNIPPET = "QFont::setPointSize"


def install_qt_message_trace_handler() -> None:
    """Install an env-gated Qt message handler for targeted local diagnostics."""

    if os.environ.get(QT_MESSAGE_TRACE_ENV, "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    from PySide6.QtCore import qInstallMessageHandler

    previous_handler = qInstallMessageHandler(None)

    def traced_handler(message_type: object, context: object, message: str) -> None:
        """Log selected Qt warnings with a local Python call stack for diagnosis."""

        if FONT_WARNING_SNIPPET in message:
            location = None
            if context is not None:
                file_name = getattr(context, "file", None)
                line_number = getattr(context, "line", None)
                function_name = getattr(context, "function", None)
                location = (
                    f"{file_name}:{line_number}:{function_name}"
                    if file_name or line_number or function_name
                    else None
                )
            log_warning(
                _LOGGER,
                "Captured Qt font warning",
                qt_message=message,
                location=location,
                stack="".join(traceback.format_stack(limit=25)).strip(),
            )

        if callable(previous_handler):
            previous_handler(message_type, context, message)

    qInstallMessageHandler(traced_handler)


__all__ = [
    "FONT_WARNING_SNIPPET",
    "QT_MESSAGE_TRACE_ENV",
    "install_qt_message_trace_handler",
]
