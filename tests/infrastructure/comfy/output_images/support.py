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

"""Build deterministic final-image infrastructure fixtures."""

from __future__ import annotations

import io

from PIL import Image

from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)


def build_source_identity(alias: str) -> OutputSourceIdentity:
    """Return one deterministic Output source identity."""

    return OutputSourceIdentity(
        node_id="node",
        source_key=f"workflow:{alias}",
        source_label=alias,
        cube_alias=alias,
    )


def build_png_bytes(width: int = 64, height: int = 48) -> bytes:
    """Return a deterministic RGBA PNG payload."""

    buffer = io.BytesIO()
    Image.new("RGBA", (width, height), (255, 64, 128, 192)).save(
        buffer,
        format="PNG",
    )
    return buffer.getvalue()


__all__ = ["build_png_bytes", "build_source_identity"]
