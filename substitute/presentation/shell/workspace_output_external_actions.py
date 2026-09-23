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

"""Own external-editor and file-reveal actions for Output assets."""

from __future__ import annotations

from typing import Protocol

from substitute.application.ports.file_manager_gateway import FileRevealResult


class _CanvasIoProtocol(Protocol):
    """Expose external editor actions for Output images."""

    def open_image_in_external_editor(
        self,
        *,
        image: object,
        image_meta: object,
    ) -> bool:
        """Open one image in the configured external editor."""

    def open_images_in_external_editor(
        self,
        *,
        images: list[tuple[object, object]],
    ) -> bool:
        """Open multiple images in the configured external editor."""


class AssetRevealServiceProtocol(Protocol):
    """Expose application-owned local asset reveal behavior."""

    def reveal_asset(self, asset_path: str) -> FileRevealResult:
        """Reveal one metadata-backed local asset path."""


class WorkspaceOutputExternalView(Protocol):
    """Describe the workspace boundary used by external Output actions."""

    canvas_io_service: _CanvasIoProtocol


class WorkspaceOutputExternalActions:
    """Adapt Output asset intent to external application services."""

    def __init__(
        self,
        view: WorkspaceOutputExternalView,
        *,
        asset_reveal_service: AssetRevealServiceProtocol | None = None,
    ) -> None:
        """Store canvas IO and optional file-reveal boundaries."""

        self._view = view
        self._asset_reveal_service = asset_reveal_service

    def open_image_in_external_editor(
        self,
        image: object,
        image_meta: object,
    ) -> bool:
        """Open one output image in the configured external editor."""

        return bool(
            self._view.canvas_io_service.open_image_in_external_editor(
                image=image,
                image_meta=image_meta,
            )
        )

    def open_images_in_external_editor(
        self,
        images: list[tuple[object, object]],
    ) -> bool:
        """Open all selected output images in the external editor."""

        return bool(
            self._view.canvas_io_service.open_images_in_external_editor(images=images)
        )

    def reveal_output_asset(self, image_meta: object) -> bool:
        """Reveal one output asset through the application-owned file manager flow."""

        if self._asset_reveal_service is None:
            return False
        asset_path = getattr(image_meta, "path", None)
        if not isinstance(asset_path, str):
            return False
        return self._asset_reveal_service.reveal_asset(asset_path).succeeded


__all__ = [
    "AssetRevealServiceProtocol",
    "WorkspaceOutputExternalActions",
    "WorkspaceOutputExternalView",
]
