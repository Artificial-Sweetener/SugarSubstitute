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

"""Own one explicit whole-layer coverage preview transaction."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import QObject, Signal
from cutecanvas import LayerEdgeModificationResult, LayerEdgeOperation

from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputLayerCoverageEditSession(QObject):
    """Own latest-value previews until an explicit Apply or Cancel action."""

    finished = Signal(object)

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QObject,
    ) -> None:
        """Bind CuteCanvas preview commands and terminal result observation."""
        super().__init__(parent)
        self._document = document
        self._mask_id: UUID | None = None
        self._session_id: UUID | None = None
        document.layerEdgeModificationCompleted.connect(self._completed)

    @property
    def active(self) -> bool:
        """Return whether a transient preview session is open."""
        return self._session_id is not None

    def begin(self, mask_id: UUID) -> bool:
        """Capture one mask revision for a new explicit preview lifetime."""
        self.cancel()
        session_id = self._document.begin_mask_edge_preview(mask_id)
        if session_id is None:
            return False
        self._session_id = session_id
        self._mask_id = mask_id
        return True

    def preview(self, operation: LayerEdgeOperation, radius: float) -> bool:
        """Publish the latest preview value without requesting settlement."""
        session_id = self._session_id
        if session_id is None:
            return False
        request_id = self._document.update_layer_edge_preview(
            session_id,
            operation,
            radius,
        )
        if request_id is None:
            self.cancel()
            return False
        return True

    def apply(self) -> bool:
        """Request atomic adoption after the latest product becomes ready."""
        session_id = self._session_id
        return bool(
            session_id is not None
            and self._document.settle_layer_edge_preview(session_id)
        )

    def cancel(self) -> bool:
        """Restore durable presentation without adding history."""
        session_id = self._session_id
        self._session_id = None
        self._mask_id = None
        return bool(
            session_id is not None
            and self._document.cancel_layer_edge_preview(session_id)
        )

    def _completed(self, result: object) -> None:
        """Release local state only for this session's terminal result."""
        if (
            not isinstance(result, LayerEdgeModificationResult)
            or result.session_id != self._session_id
        ):
            return
        self._session_id = None
        self._mask_id = None
        self.finished.emit(result)


__all__ = ["InputLayerCoverageEditSession"]
