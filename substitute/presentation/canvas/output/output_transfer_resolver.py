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
from substitute.infrastructure.persistence.output_transfer_artifact_store import (
    OutputTransferArtifact,
    OutputTransferArtifactStore,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument


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
    ) -> None:
        """Bind document identity, preference snapshot, and product authorization."""

        self._document = document
        self._preference_service = preference_service
        self._artifact_store = artifact_store
        self._is_image_authorized = is_image_authorized

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
        if artifact is None:
            return None
        if self._authorized_image_id(reference) != image_id:
            artifact.release()
            return None
        return ResolvedOutputTransfer(
            image_id=image_id,
            reference=reference,
            artifact=artifact,
        )

    def _authorized_image_id(self, reference: CanvasContentReference) -> UUID | None:
        """Return the captured image only when both document and product scopes allow it."""

        image_id = self._document.image_id_for_content_reference(reference)
        if image_id is None or not self._is_image_authorized(image_id):
            return None
        return image_id


__all__ = ["OutputTransferResolver", "ResolvedOutputTransfer"]
