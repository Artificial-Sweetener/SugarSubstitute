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

"""Build reusable Output canvas projection and image test models."""

from __future__ import annotations

from typing import Any


def session_for_projection(projection: Any, *, workflow_id: str = "wf") -> object:
    """Return an Output session wrapper for widget projection tests."""

    from substitute.application.workflows.output_canvas_session import (  # noqa: PLC0415
        bind_output_canvas_session,
    )
    from substitute.domain.workflow import CanvasSessionBoundary  # noqa: PLC0415

    metadata = {
        item.image_id: item.image_meta
        for source in projection.sources
        for item in source.images_by_set.values()
    }
    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup=metadata,
    )


class ImageSizeStub:
    """Expose the subset of the Qt image-size API used by canvas tests."""

    def __init__(self, width: int, height: int) -> None:
        """Store deterministic test dimensions."""

        self._width = width
        self._height = height

    def width(self) -> int:
        """Return the configured width."""

        return self._width

    def height(self) -> int:
        """Return the configured height."""

        return self._height


class ImageStub:
    """Test image double exposing a Qt-like size."""

    def __init__(self, width: int, height: int) -> None:
        """Store a reusable Qt-like size object for the fake image."""

        self._size = ImageSizeStub(width, height)

    def size(self) -> ImageSizeStub:
        """Return a Qt-like size object."""

        return self._size


__all__ = ["ImageSizeStub", "ImageStub", "session_for_projection"]
