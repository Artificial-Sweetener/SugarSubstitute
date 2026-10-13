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

"""Own paint acknowledgement and deadlines for exact window presentation batches."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocationOutcome,
)
from sugarsubstitute_shared.qt_window_presentation import request_window_presentation

_LOGGER = logging.getLogger(__name__)


class InvocationCompletion(Protocol):
    """Return an exact invocation's presentation result to its supervisor."""

    def __call__(
        self, request_id: str, *, outcome: ApplicationInvocationOutcome, surface: str
    ) -> None:
        """Publish one terminal presentation receipt."""


@dataclass(slots=True)
class _WindowPresentation:
    """Retain one paint batch so an obsolete deadline cannot affect its successor."""

    window: QWidget
    request_ids: list[str]


class QtInvocationPresentation:
    """Coalesce invocation receipts under one exact surface's next paint."""

    def __init__(self, complete_invocation: InvocationCompletion) -> None:
        """Bind the supervisor boundary without owning application window selection."""
        self._complete_invocation = complete_invocation
        self._pending: dict[int, _WindowPresentation] = {}

    def present(self, window: QWidget, request_ids: tuple[str, ...]) -> None:
        """Register work before activation can synchronously paint its surface."""
        key = id(window)
        presentation = self._pending.get(key)
        if presentation is None:
            presentation = _WindowPresentation(window, [])
            self._pending[key] = presentation
            QTimer.singleShot(
                2000,
                window,
                lambda: self._complete(presentation, outcome="unavailable"),
            )
        presentation.request_ids.extend(request_ids)
        _LOGGER.info(
            "Requested application surface presentation | surface=%s | request_ids=%s",
            type(window).__name__,
            ",".join(request_ids),
        )
        request_window_presentation(window)
        window.update()

    def complete_window(
        self, window: QWidget, *, outcome: ApplicationInvocationOutcome
    ) -> None:
        """Complete only the batch currently waiting for this exact surface."""
        presentation = self._pending.get(id(window))
        if presentation is not None and presentation.window is window:
            self._complete(presentation, outcome=outcome)

    def close(self) -> None:
        """Release every outstanding batch before application control disconnects."""
        for presentation in tuple(self._pending.values()):
            self._complete(presentation, outcome="unavailable")

    def _complete(
        self,
        presentation: _WindowPresentation,
        *,
        outcome: ApplicationInvocationOutcome,
    ) -> None:
        """Ignore obsolete callbacks even when their QWidget is reused for new work."""
        key = id(presentation.window)
        if self._pending.get(key) is not presentation:
            return
        del self._pending[key]
        surface = type(presentation.window).__name__
        for request_id in presentation.request_ids:
            _LOGGER.info(
                "Completed application surface presentation | request_id=%s | "
                "surface=%s | outcome=%s",
                request_id,
                surface,
                outcome,
            )
            self._complete_invocation(request_id, outcome=outcome, surface=surface)
