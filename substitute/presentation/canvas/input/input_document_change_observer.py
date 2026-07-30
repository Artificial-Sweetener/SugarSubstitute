#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
"""Route durable Input document edits to shell dirty state and autosave."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


class SignalPort(Protocol):
    """Describe the Qt signal surface needed by the observer."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect one document-change callback."""


class InputDocumentChangeObserver:
    """Observe durable mask edits without flattening the in-memory document."""

    def __init__(
        self,
        *,
        changed: SignalPort,
        active_workflow_id: Callable[[], str],
        mark_workflow_changed: Callable[[str], None],
        request_autosave: Callable[[], None],
    ) -> None:
        """Bind one document signal to workflow invalidation and persistence."""
        self._active_workflow_id = active_workflow_id
        self._mark_workflow_changed = mark_workflow_changed
        self._request_autosave = request_autosave
        changed.connect(self._document_changed)

    def _document_changed(self, *_args: object) -> None:
        """Persist the authoritative document after one durable edit."""
        workflow_id = self._active_workflow_id()
        if workflow_id:
            self._mark_workflow_changed(workflow_id)
        self._request_autosave()


__all__ = ["InputDocumentChangeObserver"]
