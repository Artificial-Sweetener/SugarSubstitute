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

"""Convert resolved Output transfer artifacts into native drag and clipboard data."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QUrl
from cutecanvas import OutboundDragPayload, OutboundMimeItem

from substitute.presentation.canvas.output.output_transfer_resolver import (
    ResolvedOutputTransfer,
)


def drag_payload_for_transfer(
    resolved: ResolvedOutputTransfer,
) -> OutboundDragPayload:
    """Build one native drag payload from the selected representation only."""

    artifact = resolved.artifact
    return OutboundDragPayload(
        items=(OutboundMimeItem(artifact.mime_type, artifact.data),),
        urls=(QUrl.fromLocalFile(str(artifact.path)),),
        preview=artifact.image,
    )


def mime_data_for_transfer(resolved: ResolvedOutputTransfer) -> QMimeData:
    """Build clipboard MIME data from the selected representation only."""

    artifact = resolved.artifact
    mime_data = QMimeData()
    mime_data.setUrls((QUrl.fromLocalFile(str(artifact.path)),))
    mime_data.setData(artifact.mime_type, artifact.data)
    mime_data.setImageData(artifact.image)
    return mime_data


__all__ = ["drag_payload_for_transfer", "mime_data_for_transfer"]
