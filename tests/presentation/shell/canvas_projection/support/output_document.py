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

"""Characterize canvas projection output-document adapter contracts."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable


from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_session import OutputCanvasSession


class _FakeOutputDocument:
    """Record document content and presentation without a QPane adapter."""

    def __init__(self) -> None:
        """Initialize output content and presentation observations."""

        self.content: dict[uuid.UUID, tuple[object, Path | None]] = {}
        self.admission_calls: list[tuple[uuid.UUID, object, Path | None]] = []
        self.active_image_id: uuid.UUID | None = None
        self.presentation_calls: list[uuid.UUID | None] = []
        self.inspection_groups: tuple[tuple[uuid.UUID, ...], ...] = ()

    @property
    def images(self) -> dict[uuid.UUID, tuple[object, Path | None]]:
        """Expose test content membership for pre-existing assertions."""

        return self.content

    @property
    def add_calls(self) -> list[tuple[uuid.UUID, object, Path | None]]:
        """Expose document admissions for pre-existing assertions."""

        return self.admission_calls

    @property
    def current_id(self) -> uuid.UUID | None:
        """Expose the document's active application image identity."""

        return self.active_image_id

    @current_id.setter
    def current_id(self, image_id: uuid.UUID | None) -> None:
        """Set the active image for characterization preconditions."""

        self.active_image_id = image_id

    @property
    def selection_calls(self) -> list[uuid.UUID | None]:
        """Expose presentation changes for pre-existing assertions."""

        return self.presentation_calls

    @property
    def linked_groups(self) -> tuple[SimpleNamespace, ...]:
        """Expose linked inspection membership for pre-existing assertions."""

        return tuple(
            SimpleNamespace(group_id=uuid.uuid4(), members=members)
            for members in self.inspection_groups
        )

    def admit_image(
        self,
        image_id: uuid.UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Record authoritative content admission."""

        if self.content.get(image_id) == (image, path):
            return
        self.content[image_id] = (image, path)
        self.admission_calls.append((image_id, image, path))

    def retire_image(self, image_id: uuid.UUID) -> None:
        """Record application-authorized document retirement."""

        self.content.pop(image_id, None)

    def present_projection(self, session: OutputCanvasSession) -> None:
        """Derive document presentation and linked inspection from a session."""

        projection = session.projection
        active_image_id = self.active_image_id
        if projection.active_set_index > 0 and not projection.active_scene_overview:
            active_image_id = projection.active_uuid
        elif active_image_id not in session.allowed_image_ids:
            active_image_id = None
        if active_image_id != self.active_image_id:
            self.active_image_id = active_image_id
            self.presentation_calls.append(active_image_id)
        members = tuple(
            dict.fromkeys(
                item.image_id
                for source in projection.sources
                for item in source.images_by_set.values()
            )
        )
        self.inspection_groups = (members,) if len(members) > 1 else ()


class _FakeOutputCanvas:
    def __init__(self, output_document: _FakeOutputDocument) -> None:
        """Initialize the session-facing host around the fake document."""

        self._output_document = output_document
        self.events: list[tuple[str, str | None]] = []
        self.sync_calls: list[Any] = []
        self.sync_session_calls: list[OutputCanvasSession] = []
        self.register_calls: list[Any] = []
        self.clear_preview_calls: list[str | None] = []
        self.prepare_calls: list[tuple[str, tuple[uuid.UUID, ...]]] = []

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Record the visible session and project it through the fake document."""

        projection = session.projection
        image_ids = tuple(
            item.image_id
            for source in projection.sources
            for item in source.images_by_set.values()
        )
        workflow_id = session.workflow_id.value
        self.events.append(("bind", workflow_id))
        self.prepare_calls.append((workflow_id, image_ids))
        self.sync_session_calls.append(session)
        self.sync_calls.append(projection)
        self._output_document.present_projection(session)

    def clear_previews(self, source_key: str | None = None) -> None:
        """Record preview retirement requested by projection lifecycle."""

        self.events.append(("clear_previews", source_key))
        self.clear_preview_calls.append(source_key)


class _FakeOutputContentSynchronizer:
    """Mirror authoritative test payloads into the fake Output document."""

    def __init__(
        self,
        registry: CanvasImageRegistry,
        output_document: _FakeOutputDocument,
    ) -> None:
        """Store the application registry and document-facing test boundary."""

        self._registry = registry
        self._output_document = output_document

    def synchronize_projection(self, projection: Any) -> None:
        """Make every projected test payload available to the fake route adapter."""

        image_ids = {
            item.image_id
            for source in projection.sources
            for item in source.images_by_set.values()
        }
        for scene in projection.scene_groups:
            if scene.primary_image_id is not None:
                image_ids.add(scene.primary_image_id)
            for source in scene.sources:
                image_ids.update(
                    item.image_id for item in source.images_by_set.values()
                )
        for image_id in image_ids:
            image = self._registry.payload_for(image_id)
            metadata = self._registry.metadata_for(image_id)
            if image is None or metadata is None:
                continue
            path = Path(metadata.path) if metadata.path else None
            self._output_document.admit_image(image_id, image, path)

    def retire_unreferenced(self, image_ids: Iterable[uuid.UUID]) -> None:
        """Remove test content after application workflow ownership releases it."""

        for image_id in image_ids:
            self._output_document.retire_image(image_id)
