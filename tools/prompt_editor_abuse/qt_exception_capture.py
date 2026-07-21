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

"""Capture uncaught Python exceptions emitted by headless Qt callbacks."""

from __future__ import annotations

import sys
from collections.abc import Callable
from types import TracebackType
from typing import Self

type ExceptionHook = Callable[
    [type[BaseException], BaseException, TracebackType | None],
    None,
]


class PromptAbuseQtExceptionCapture:
    """Turn delayed Qt callback failures into abuse-harness correctness evidence."""

    def __init__(self) -> None:
        """Create an empty exception recorder."""

        self._previous_hook: ExceptionHook | None = None
        self._violations: list[str] = []

    @property
    def violations(self) -> tuple[str, ...]:
        """Return stable, content-safe descriptions of captured exceptions."""

        return tuple(self._violations)

    def __enter__(self) -> Self:
        """Install the recorder for the bounded headless scenario."""

        if self._previous_hook is not None:
            raise RuntimeError("Qt exception capture is already active.")
        self._previous_hook = sys.excepthook
        sys.excepthook = self._capture
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore the process exception hook after the scenario."""

        del exception_type, exception, traceback
        previous_hook = self._previous_hook
        self._previous_hook = None
        if previous_hook is not None:
            sys.excepthook = previous_hook

    def _capture(
        self,
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        """Record one uncaught callback exception without serializing prompt text."""

        del traceback
        message = str(exception).strip().replace("\n", " ")
        if len(message) > 160:
            message = f"{message[:157]}..."
        self._violations.append(
            f"uncaught_qt_callback:{exception_type.__name__}:{message}"
        )


__all__ = ["PromptAbuseQtExceptionCapture"]
