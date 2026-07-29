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

"""Own the read-only CuteCanvas Output document and identity registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import QObject
from PySide6.QtGui import QImage
from cutecanvas import (
    CanvasContentKind,
    CanvasContentReference,
    CanvasDocument,
    CanvasDocumentRuntime,
    CanvasInspectionGroup,
    CanvasInteractionMode,
    CanvasViewSession,
    CanvasWorkspace,
    ComparisonOrientation,
    CompositionPolicy,
    ExecutionRuntime,
    LayerPolicy,
)

from substitute.shared.logging.logger import get_logger, log_debug, log_warning
from substitute.application.workflows.output_detail_inspection import (
    OutputDetailInspectionGroup,
)
from substitute.presentation.canvas.output.output_grid_layout_policy import (
    output_grid_layout_policy,
)
from substitute.presentation.canvas.output.output_inspection_registry import (
    OutputInspectionGroupRegistry,
)

_LOGGER = get_logger("presentation.canvas.output.output_document")

_OUTPUT_LAYER_POLICY = LayerPolicy(
    selectable=False,
    movable=False,
    pixel_editable=False,
    reorderable=False,
    removable=False,
)
_OUTPUT_COMPOSITION_POLICY = CompositionPolicy(removable=True)


@dataclass(frozen=True, slots=True)
class OutputDocumentImage:
    """Map one SugarSubstitute Output image identity to locked document content."""

    image_id: UUID
    composition_id: UUID
    path: Path | None
    payload: QImage
    payload_cache_key: int


class OutputCanvasDocument(QObject):
    """Provide one long-lived CuteCanvas Output document and workspace."""

    def __init__(
        self,
        *,
        execution_runtime: ExecutionRuntime | None = None,
    ) -> None:
        """Create the Output document, detached session, and read-only workspace."""

        super().__init__()
        self._document = CanvasDocument()
        self._runtime = CanvasDocumentRuntime(
            self._document,
            execution_runtime=execution_runtime,
        )
        self._session = CanvasViewSession()
        self._workspace = CanvasWorkspace(
            document=self._document,
            document_runtime=self._runtime,
            session=self._session,
        )
        self._workspace.setInteractionMode(CanvasInteractionMode.READ_ONLY)
        self._images: dict[UUID, OutputDocumentImage] = {}
        self._detail_groups = OutputInspectionGroupRegistry(self.composition_id_for)
        self._comparison_group_id = uuid4()
        self._closed = False

    @property
    def document(self) -> CanvasDocument:
        """Return the durable Output document."""

        return self._document

    @property
    def runtime(self) -> CanvasDocumentRuntime:
        """Return the document-scoped runtime bound to this Output document."""

        return self._runtime

    @property
    def workspace(self) -> CanvasWorkspace:
        """Return the single read-only workspace that presents this document."""

        return self._workspace

    @property
    def session(self) -> CanvasViewSession:
        """Return detached Output presentation and inspection state."""

        return self._session

    def admit_image(
        self,
        image_id: UUID,
        image: object,
        *,
        path: Path | None = None,
        title: str = "Output image",
    ) -> bool:
        """Admit one valid image as a locked Output composition.

        Returns:
            Whether document content changed.
        """

        if not isinstance(image, QImage) or image.isNull():
            log_warning(
                _LOGGER,
                "Output document image admission rejected invalid payload",
                image_id=str(image_id),
                path=str(path) if path is not None else "",
            )
            return False
        normalized_path = Path(path) if path is not None else None
        existing = self._images.get(image_id)
        if existing is not None and self._same_payload(
            existing, image, normalized_path
        ):
            return False
        if existing is not None:
            self._document.remove_composition(existing.composition_id)
        composition_id = self._document.create_composition_from_image(
            image,
            title=title,
            interaction=_OUTPUT_LAYER_POLICY,
            policy=_OUTPUT_COMPOSITION_POLICY,
        )
        self._images[image_id] = OutputDocumentImage(
            image_id=image_id,
            composition_id=composition_id,
            path=normalized_path,
            payload=QImage(image),
            payload_cache_key=image.cacheKey(),
        )
        if existing is not None:
            self._publish_detail_groups()
        log_debug(
            _LOGGER,
            "Output document image admitted",
            image_id=str(image_id),
            composition_id=str(composition_id),
            path=str(normalized_path) if normalized_path is not None else "",
            replaced=existing is not None,
        )
        return True

    def retire_image(self, image_id: UUID) -> bool:
        """Retire one already-unreferenced Output composition."""

        record = self._images.pop(image_id, None)
        if record is None:
            return False
        self._document.remove_composition(record.composition_id)
        self._publish_detail_groups()
        log_debug(
            _LOGGER,
            "Output document image retired",
            image_id=str(image_id),
            composition_id=str(record.composition_id),
        )
        return True

    def composition_id_for(self, image_id: UUID) -> UUID | None:
        """Return the live document composition for one application image."""

        record = self._images.get(image_id)
        return None if record is None else record.composition_id

    def image_ids(self) -> tuple[UUID, ...]:
        """Return registered application output identities in admission order."""

        return tuple(self._images)

    def image_ids_for_compositions(
        self,
        composition_ids: tuple[UUID, ...],
    ) -> tuple[UUID, ...]:
        """Resolve ordered live presentation targets to application identities."""

        return tuple(
            image_id
            for composition_id in composition_ids
            if (image_id := self.image_id_for_composition(composition_id)) is not None
        )

    def image_payload(self, image_id: UUID) -> QImage | None:
        """Return detached current pixels for one registered Output image."""

        record = self._images.get(image_id)
        return None if record is None else QImage(record.payload)

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the authorized canonical asset path for one Output image."""

        record = self._images.get(image_id)
        return None if record is None or record.path is None else Path(record.path)

    def image_id_for_composition(self, composition_id: UUID) -> UUID | None:
        """Resolve one document composition identity to application output identity."""

        for image_id, record in self._images.items():
            if record.composition_id == composition_id:
                return image_id
        return None

    def content_reference_for(self, image_id: UUID) -> CanvasContentReference | None:
        """Return a stable current content reference for one Output image."""

        composition_id = self.composition_id_for(image_id)
        return (
            None
            if composition_id is None
            else self._document.content_reference(composition_id)
        )

    def image_id_for_content_reference(
        self,
        reference: CanvasContentReference,
    ) -> UUID | None:
        """Resolve a current Output composition reference without stale fallback."""

        if (
            reference.kind is not CanvasContentKind.COMPOSITION
            or reference.composition_id is None
        ):
            return None
        try:
            resolved = self._document.resolve_content(reference)
        except (KeyError, ValueError):
            return None
        if resolved.stale:
            return None
        return self.image_id_for_composition(reference.composition_id)

    def set_detail_inspection_groups(
        self,
        *,
        workflow_id: str,
        groups: tuple[OutputDetailInspectionGroup, ...],
    ) -> None:
        """Publish scoped detail groups while retaining inactive workflow state."""

        self._detail_groups.replace_workflow_groups(
            workflow_id,
            groups,
        )
        self._publish_detail_groups()

    def present_single(self, image_id: UUID) -> bool:
        """Present one registered Output image in its native composition view."""

        composition_id = self.composition_id_for(image_id)
        if composition_id is None:
            return False
        self._workspace.setSinglePresentation(composition_id)
        return True

    def present_grid(self, image_ids: tuple[UUID, ...]) -> bool:
        """Present ordered registered Output images through workspace grid reflow."""

        composition_ids = self._composition_ids_for(image_ids)
        if not composition_ids:
            self.clear_presentation()
            return False
        self._workspace.setGridPresentation(
            composition_ids,
            policy=output_grid_layout_policy(),
        )
        return True

    def present_comparison(
        self,
        primary_image_id: UUID,
        secondary_image_id: UUID,
        *,
        split_position: float,
        orientation: str,
    ) -> bool:
        """Present two linked Output images with one transient reveal divider."""

        primary_id = self.composition_id_for(primary_image_id)
        secondary_id = self.composition_id_for(secondary_image_id)
        if primary_id is None or secondary_id is None or primary_id == secondary_id:
            return False
        self._workspace.setComparisonInspectionGroups(
            (
                CanvasInspectionGroup(
                    self._comparison_group_id, (primary_id, secondary_id)
                ),
            )
        )
        self._workspace.setComparisonPresentation(
            primary_id,
            secondary_id,
            split_position=split_position,
            orientation=ComparisonOrientation(orientation),
        )
        return True

    def clear_presentation(self) -> None:
        """Clear visible Output targets while retaining admitted document content."""

        self._workspace.setInspectionGroups(())
        self._workspace.setComparisonInspectionGroups(())
        self._workspace.setTabbedPresentation(())
        self._session.clear_activation()

    def close(self) -> None:
        """Release workspace, document runtime, and durable document in dependency order."""

        if self._closed:
            return
        self._closed = True
        self._workspace.close()
        self._runtime.close()
        self._document.close()
        self._detail_groups.clear()
        self._images.clear()

    @staticmethod
    def _same_payload(
        record: OutputDocumentImage,
        image: QImage,
        path: Path | None,
    ) -> bool:
        """Compare host payload identity without inspecting document resources."""

        return record.payload_cache_key == image.cacheKey() and record.path == path

    def _composition_ids_for(self, image_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
        """Resolve ordered unique application identities to live composition IDs."""

        composition_ids: list[UUID] = []
        for image_id in image_ids:
            composition_id = self.composition_id_for(image_id)
            if composition_id is not None and composition_id not in composition_ids:
                composition_ids.append(composition_id)
        return tuple(composition_ids)

    def _publish_detail_groups(self) -> None:
        """Publish every retained definition that has at least two live targets."""

        self._workspace.setInspectionGroups(self._detail_groups.live_groups())


__all__ = ["OutputCanvasDocument", "OutputDocumentImage"]
