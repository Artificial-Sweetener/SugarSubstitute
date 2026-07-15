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

"""Define CivitAI model download organization preferences and render context."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN = "{base_model}\\{file_name}"


@dataclass(frozen=True, slots=True)
class CivitaiDownloadPathToken:
    """Describe one supported CivitAI download path token."""

    name: str
    description: str

    @property
    def placeholder(self) -> str:
        """Return the literal placeholder inserted into editable patterns."""

        return f"{{{self.name}}}"


@dataclass(frozen=True, slots=True)
class CivitaiDownloadPathRenderContext:
    """Provide CivitAI metadata used to render a download destination."""

    kind: str
    comfy_root: Path
    base_model: str
    model_name: str
    version_name: str
    creator: str
    file_name: str

    @property
    def file_stem(self) -> str:
        """Return the CivitAI file name without its extension."""

        return Path(self.file_name).stem


@dataclass(frozen=True, slots=True)
class CivitaiDownloadPathRenderResult:
    """Carry a rendered CivitAI download path for previews."""

    path: Path
    relative_path: Path
    display_path: str


SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS: tuple[CivitaiDownloadPathToken, ...] = (
    CivitaiDownloadPathToken("base_model", "Base model folder"),
    CivitaiDownloadPathToken("model_name", "CivitAI model name"),
    CivitaiDownloadPathToken("version_name", "CivitAI version name"),
    CivitaiDownloadPathToken("creator", "CivitAI creator"),
    CivitaiDownloadPathToken("file_name", "File name"),
    CivitaiDownloadPathToken("file_stem", "File name without extension"),
)

SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES = frozenset(
    token.name for token in SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS
)


__all__ = [
    "DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN",
    "CivitaiDownloadPathRenderContext",
    "CivitaiDownloadPathRenderResult",
    "CivitaiDownloadPathToken",
    "SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKEN_NAMES",
    "SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS",
]
