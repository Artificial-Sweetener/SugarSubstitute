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

"""Define strict live Output visual event boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from substitute.application.ports.comfy_gateway import (
        OutputImageUpdate,
        PreviewImageUpdate,
    )


@dataclass(frozen=True, slots=True)
class OutputSceneIdentity:
    """Identify a complete backend scene route for live visual placement."""

    run_id: str
    key: str
    title: str
    order: int
    count: int


@dataclass(frozen=True, slots=True)
class SourceOnlyOutputIdentity:
    """Mark a live output route that belongs only to an output source."""


OutputVisualScene = OutputSceneIdentity | SourceOnlyOutputIdentity


@dataclass(frozen=True, slots=True)
class OutputVisualIdentity:
    """Identify one live generated visual using backend-provided authority."""

    workflow_id: str
    generation_run_id: str
    prompt_id: str
    client_id: str
    source_key: str
    source_label: str
    scene: OutputVisualScene

    @classmethod
    def from_update(
        cls,
        update: "PreviewImageUpdate | OutputImageUpdate",
    ) -> "OutputVisualIdentity | None":
        """Return strict live identity when every required field is present."""

        if (
            not update.workflow_id
            or not update.generation_run_id
            or not update.prompt_id
            or not update.client_id
            or not update.source_key
            or not update.source_label
        ):
            return None
        scene = _scene_identity_from_update(update)
        if scene is None:
            return None
        return cls(
            workflow_id=update.workflow_id,
            generation_run_id=update.generation_run_id,
            prompt_id=update.prompt_id,
            client_id=update.client_id,
            source_key=update.source_key,
            source_label=update.source_label,
            scene=scene,
        )


@dataclass(frozen=True, slots=True)
class PreviewNodeIdentity:
    """Preserve backend preview node metadata after source normalization."""

    resolved_node_id: str
    metadata_node_id: str | None
    display_node_id: str | None
    parent_node_id: str | None
    real_node_id: str | None


@dataclass(frozen=True, slots=True)
class LivePreviewEvent:
    """Carry a strict backend-identified transient preview image."""

    identity: OutputVisualIdentity
    image: object
    node_identity: PreviewNodeIdentity

    @classmethod
    def from_update(
        cls,
        update: "PreviewImageUpdate",
    ) -> "LivePreviewEvent | None":
        """Return a strict live preview event, or reject incomplete updates."""

        identity = OutputVisualIdentity.from_update(update)
        if identity is None or not update.node_id:
            return None
        return cls(
            identity=identity,
            image=update.image,
            node_identity=PreviewNodeIdentity(
                resolved_node_id=update.node_id,
                metadata_node_id=update.metadata_node_id,
                display_node_id=update.display_node_id,
                parent_node_id=update.parent_node_id,
                real_node_id=update.real_node_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class LiveFinalOutputEvent:
    """Carry a strict backend-identified final image placement event."""

    identity: OutputVisualIdentity
    node_id: str
    workflow_payload: Mapping[str, object]
    file_path: Path
    list_index: int
    artifact_width: int
    artifact_height: int

    @classmethod
    def from_update(
        cls,
        update: "OutputImageUpdate",
    ) -> "LiveFinalOutputEvent | None":
        """Return a strict live final event, or reject incomplete updates."""

        identity = OutputVisualIdentity.from_update(update)
        if (
            identity is None
            or not update.node_id
            or not _is_non_negative_int(update.list_index)
            or not _is_positive_int(update.artifact_width)
            or not _is_positive_int(update.artifact_height)
        ):
            return None
        return cls(
            identity=identity,
            node_id=update.node_id,
            workflow_payload=update.workflow_payload,
            file_path=update.file_path,
            list_index=update.list_index,
            artifact_width=update.artifact_width,
            artifact_height=update.artifact_height,
        )


def _scene_identity_from_update(
    update: "PreviewImageUpdate | OutputImageUpdate",
) -> OutputVisualScene | None:
    """Return source-only or complete scene identity from transport fields."""

    scene_values = (
        update.scene_run_id,
        update.scene_key,
        update.scene_title,
        update.scene_order,
        update.scene_count,
    )
    if all(value is None for value in scene_values):
        return SourceOnlyOutputIdentity()
    if (
        update.scene_run_id
        and update.scene_key
        and update.scene_title
        and isinstance(update.scene_order, int)
        and isinstance(update.scene_count, int)
    ):
        return OutputSceneIdentity(
            run_id=update.scene_run_id,
            key=update.scene_key,
            title=update.scene_title,
            order=update.scene_order,
            count=update.scene_count,
        )
    return None


def _is_non_negative_int(value: object) -> TypeGuard[int]:
    """Return whether value is a backend list index."""

    return type(value) is int and value >= 0


def _is_positive_int(value: object) -> TypeGuard[int]:
    """Return whether value is a concrete artifact dimension."""

    return type(value) is int and value > 0


__all__ = [
    "LiveFinalOutputEvent",
    "LivePreviewEvent",
    "OutputSceneIdentity",
    "OutputVisualIdentity",
    "PreviewNodeIdentity",
    "SourceOnlyOutputIdentity",
]
