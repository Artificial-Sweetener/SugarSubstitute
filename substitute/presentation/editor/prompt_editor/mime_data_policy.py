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

"""Classify external MIME payloads before they can mutate prompt source text."""

from __future__ import annotations

from PySide6.QtCore import QMimeData


_PLAIN_TEXT_MIME = "text/plain"


def mime_data_has_prompt_plain_text(mime_data: QMimeData | None) -> bool:
    """Return whether MIME data contains text safe for prompt-source insertion."""

    return prompt_plain_text_from_mime_data(mime_data) is not None


def prompt_plain_text_from_mime_data(mime_data: QMimeData | None) -> str | None:
    """Return prompt-safe plain text from one MIME payload, if present."""

    if mime_data is None:
        return None
    if _mime_data_contains_external_rich_or_file_payload(mime_data):
        return None
    if not mime_data.hasText() or not mime_data.hasFormat(_PLAIN_TEXT_MIME):
        return None
    return mime_data.text()


def _mime_data_contains_external_rich_or_file_payload(mime_data: QMimeData) -> bool:
    """Return whether MIME data can coerce non-prompt content into source text."""

    return bool(
        mime_data.hasUrls()
        or mime_data.hasImage()
        or mime_data.hasHtml()
        or _mime_formats_include_file_payload(mime_data.formats())
    )


def _mime_formats_include_file_payload(formats: list[str]) -> bool:
    """Return whether platform-specific MIME formats describe dropped files."""

    normalized_formats = {mime_format.casefold() for mime_format in formats}
    return bool(
        "text/uri-list" in normalized_formats
        or "application/x-qt-image" in normalized_formats
        or any(
            mime_format.startswith('application/x-qt-windows-mime;value="file')
            for mime_format in normalized_formats
        )
    )


__all__ = [
    "mime_data_has_prompt_plain_text",
    "prompt_plain_text_from_mime_data",
]
