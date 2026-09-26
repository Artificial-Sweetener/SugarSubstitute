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

"""Authorize one captured Output document subject for outbound transfer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from cutecanvas import CanvasContentReference

from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.domain.generation import effective_output_transfer_format
from substitute.domain.output_media import OutputMediaKind
from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifact,
    OutputTransferArtifactStore,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.shared.types import OutputImageMeta


@dataclass(frozen=True, slots=True)
class ResolvedOutputTransfer:
    """Bind one captured document revision to its selected transfer artifact."""

    image_id: UUID
    reference: CanvasContentReference
    artifact: OutputTransferArtifact


class OutputTransferResolver:
    """Resolve only authorized, current Output document content for transfer."""

    def __init__(
        self,
        *,
        document: OutputCanvasDocument,
        preference_service: OutputPreferenceService,
        artifact_store: OutputTransferArtifactStore,
        is_image_authorized: Callable[[UUID], bool],
        metadata_for: Callable[[UUID], OutputImageMeta | None] | None = None,
    ) -> None:
        """Bind document identity, preference snapshot, and product authorization."""

        self._document = document
        self._preference_service = preference_service
        self._artifact_store = artifact_store
        self._is_image_authorized = is_image_authorized
        self._metadata_for = metadata_for

    def resolve(
        self,
        reference: CanvasContentReference,
        *,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> ResolvedOutputTransfer | None:
        """Materialize a captured subject only while its document identity remains live."""

        image_id = self._authorized_image_id(reference)
        if image_id is None:
            return None
        metadata = (
            self._metadata_for(image_id) if self._metadata_for is not None else None
        )
        if metadata is not None and metadata.media_kind is OutputMediaKind.VIDEO:
            artifact = self._artifact_store.reference_file(
                self._document.image_path(image_id),
                mime_type=metadata.mime_type,
            )
            return self._resolved_if_still_authorized(reference, image_id, artifact)
        image = self._document.image_payload(image_id)
        if image is None:
            return None
        preferences = self._preference_service.load_preferences()
        artifact = self._artifact_store.materialize(
            image,
            canonical_path=self._document.image_path(image_id),
            transfer_format=effective_output_transfer_format(preferences),
            jpeg_settings=preferences.jpeg,
            cancellation_requested=cancellation_requested,
        )
        return self._resolved_if_still_authorized(reference, image_id, artifact)

    def _resolved_if_still_authorized(
        self,
        reference: CanvasContentReference,
        image_id: UUID,
        artifact: OutputTransferArtifact | None,
    ) -> ResolvedOutputTransfer | None:
        """Return an artifact only while its captured subject remains current."""

        if artifact is None:
            return None
        if self._authorized_image_id(reference) != image_id:
            artifact.release()
            return None
        return ResolvedOutputTransfer(image_id, reference, artifact)

    def _authorized_image_id(self, reference: CanvasContentReference) -> UUID | None:
        """Return the captured image only when both document and product scopes allow it."""

        image_id = self._document.image_id_for_content_reference(reference)
        if image_id is None or not self._is_image_authorized(image_id):
            return None
        return image_id


__all__ = ["OutputTransferResolver", "ResolvedOutputTransfer"]
