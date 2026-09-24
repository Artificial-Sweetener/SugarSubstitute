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

"""Coalesce prompt text-change search refreshes onto the Qt event loop."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QTimer


class SignalConnectorProtocol(Protocol):
    """Describe a Qt-like signal that accepts connected callbacks."""

    def connect(self, callback: Callable[[], None]) -> None:
        """Connect one callback to the signal."""


class SearchPromptEditorProtocol(Protocol):
    """Describe prompt editor APIs used by search refresh scheduling."""

    textChanged: SignalConnectorProtocol

    def property(self, name: str) -> object:
        """Return one dynamic Qt property."""

    def setProperty(self, name: str, value: object) -> object:
        """Set one dynamic Qt property."""

    def clear_search_matches(self) -> None:
        """Clear rendered text-search ranges."""


class SearchRefreshScheduler:
    """Own idempotent prompt wiring and one queued refresh callback."""

    def __init__(
        self,
        *,
        on_pending_changed: Callable[[bool], None],
        on_refresh: Callable[[], None],
    ) -> None:
        """Store callbacks and initialize without queued work."""

        self._on_pending_changed = on_pending_changed
        self._on_refresh = on_refresh
        self._pending = False

    @property
    def pending(self) -> bool:
        """Return whether a text-search refresh is queued."""

        return self._pending

    def configure(
        self,
        prompt_editor: SearchPromptEditorProtocol,
        schedule: Callable[[SearchPromptEditorProtocol | None], None],
    ) -> None:
        """Connect one prompt editor to active search recomputation once."""

        if prompt_editor.property("promptTextSearchRefreshTracked") is True:
            return
        prompt_editor.setProperty("promptTextSearchRefreshTracked", True)
        prompt_editor.textChanged.connect(lambda: schedule(prompt_editor))

    def schedule(self, prompt_editor: SearchPromptEditorProtocol | None = None) -> None:
        """Clear stale ranges and coalesce one event-loop refresh."""

        if prompt_editor is not None:
            prompt_editor.clear_search_matches()
        if self._pending:
            return
        self._pending = True
        self._on_pending_changed(True)
        QTimer.singleShot(0, self._run)

    def _run(self) -> None:
        """Publish settlement before invoking the scheduled refresh."""

        self._pending = False
        self._on_pending_changed(False)
        self._on_refresh()


__all__ = [
    "SearchPromptEditorProtocol",
    "SearchRefreshScheduler",
    "SignalConnectorProtocol",
]
