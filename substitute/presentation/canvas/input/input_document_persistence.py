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

"""Persist complete Input editor authority through CuteCanvas public APIs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from cutecanvas import CanvasDocument, CuteCanvas

from substitute.application.workspace_state.session_persistence import (
    PreparedSessionPersistence,
)


class InputDocumentPersistence:
    """Own complete editable Input document save and restore operations."""

    def __init__(
        self,
        *,
        document: CanvasDocument,
        canvas: CuteCanvas,
        install_restored_compositions: Callable[[tuple[UUID, ...]], None],
    ) -> None:
        """Bind document persistence and application identity restoration."""
        self._document = document
        self._canvas = canvas
        self._install_restored_compositions = install_restored_compositions

    def has_editable_content(self) -> bool:
        """Return whether the document owns at least one Input composition."""
        return bool(self._document.composition_ids())

    def save_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Atomically persist every Input composition and editable resource."""
        handles = self._canvas.editor.persistence.save_document(path)
        return tuple(handle.id for handle in handles)

    def prepare_editable_document_save(
        self,
        path: Path,
    ) -> PreparedSessionPersistence:
        """Capture authority now and defer only detached archive I/O."""
        persistence = self._canvas.editor.persistence
        snapshot = persistence.capture_document()

        def persist() -> None:
            """Write the immutable capture without consulting live Qt state."""
            persistence.write_document(snapshot, path)

        return PreparedSessionPersistence("editable_input_document", persist)

    def restore_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Restore one complete Input document before image payload hydration."""
        if self._document.composition_ids():
            raise RuntimeError("Input document restore requires an empty document")
        handles = self._canvas.editor.persistence.load_document(
            path,
            open_first=False,
        )
        composition_ids = tuple(handle.id for handle in handles)
        self._install_restored_compositions(composition_ids)
        return composition_ids


__all__ = ["InputDocumentPersistence"]
