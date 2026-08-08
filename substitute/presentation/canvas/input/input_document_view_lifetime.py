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

"""Close one Input document only after every mounted CuteCanvas view is gone."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget


class InputDocumentViewLifetime:
    """Own mounted-view teardown ordering for one shared Input runtime."""

    def __init__(self, finalize_document: Callable[[], None]) -> None:
        """Store the terminal document callback invoked after the last view dies."""

        self._finalize_document = finalize_document
        self._views: dict[int, QWidget] = {}
        self._close_requested = False
        self._finalized = False

    def register(self, view: QWidget) -> None:
        """Retain one mounted view until Qt confirms its destruction."""

        if self._close_requested:
            raise RuntimeError("cannot mount an Input view after document close")
        view_key = id(view)
        if view_key in self._views:
            return
        self._views[view_key] = view
        view.destroyed.connect(partial(self._release_view, view_key))

    def close(self) -> None:
        """Request every view's destruction before finalizing the document."""

        if self._close_requested:
            return
        self._close_requested = True
        for view in tuple(self._views.values()):
            view.close()
            view.deleteLater()
        self._finalize_if_ready()

    def _release_view(self, view_key: int, _object: QObject | None = None) -> None:
        """Release one destroyed view and finalize after the last release."""

        self._views.pop(view_key, None)
        self._finalize_if_ready()

    def _finalize_if_ready(self) -> None:
        """Finalize exactly once after close was requested and no views remain."""

        if self._finalized or not self._close_requested or self._views:
            return
        self._finalized = True
        self._finalize_document()


__all__ = ["InputDocumentViewLifetime"]
