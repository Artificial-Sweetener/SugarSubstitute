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

"""Build Comfy artifact URLs from typed endpoint configuration."""

from __future__ import annotations

from urllib.parse import urlencode

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact


def artifact_view_url(endpoint: ComfyEndpoint, artifact: ComfyImageArtifact) -> str:
    """Return the encoded Comfy ``/view`` URL for one artifact."""

    query = urlencode(
        {
            "filename": artifact.filename,
            "subfolder": artifact.subfolder,
            "type": artifact.type,
        }
    )
    return f"{endpoint.view_url()}?{query}"
