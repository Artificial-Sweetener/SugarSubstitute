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

"""Tests for prompt-editor MIME data acceptance policy."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QImage

from substitute.presentation.editor.prompt_editor.mime_data_policy import (
    mime_data_has_prompt_plain_text,
    prompt_plain_text_from_mime_data,
)


def test_prompt_mime_policy_accepts_plain_text_only() -> None:
    """Plain text MIME data should remain available for prompt insertion."""

    mime_data = QMimeData()
    mime_data.setText("1girl, cinematic lighting")

    assert mime_data_has_prompt_plain_text(mime_data)
    assert prompt_plain_text_from_mime_data(mime_data) == "1girl, cinematic lighting"


def test_prompt_mime_policy_rejects_url_text_coercion() -> None:
    """File drops should not become prompt text through Qt URL coercion."""

    mime_data = QMimeData()
    mime_data.setText("E:/ComfyUI/output/example.png")
    mime_data.setUrls([QUrl.fromLocalFile("E:/ComfyUI/output/example.png")])

    assert not mime_data_has_prompt_plain_text(mime_data)
    assert prompt_plain_text_from_mime_data(mime_data) is None


def test_prompt_mime_policy_rejects_image_payloads() -> None:
    """Image MIME data should not be inserted as prompt source text."""

    mime_data = QMimeData()
    mime_data.setText("rendered image")
    mime_data.setImageData(QImage(1, 1, QImage.Format.Format_ARGB32))

    assert prompt_plain_text_from_mime_data(mime_data) is None


def test_prompt_mime_policy_rejects_html_payloads() -> None:
    """Rich HTML drags should not bypass the plain-text-only policy."""

    mime_data = QMimeData()
    mime_data.setText("bold prompt")
    mime_data.setHtml("<strong>bold prompt</strong>")

    assert prompt_plain_text_from_mime_data(mime_data) is None


def test_prompt_mime_policy_rejects_windows_file_formats() -> None:
    """Windows shell file MIME markers should block text fallback insertion."""

    mime_data = QMimeData()
    mime_data.setText("C:/Users/imkno/Pictures/render.png")
    mime_data.setData(
        'application/x-qt-windows-mime;value="FileNameW"',
        b"C:/Users/imkno/Pictures/render.png",
    )

    assert prompt_plain_text_from_mime_data(mime_data) is None
