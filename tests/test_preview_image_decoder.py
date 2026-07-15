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

"""Tests for Qt-free Comfy preview image byte decoding."""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from substitute.infrastructure.comfy.preview_image_decoder import decode_preview_image

_DECODER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "preview_image_decoder.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _png_bytes(
    mode: str,
    size: tuple[int, int],
    color: tuple[int, ...],
) -> bytes:
    """Return encoded PNG bytes for one in-memory test image."""

    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_preview_image_decoder_imports_no_ui_or_listener_boundaries() -> None:
    """Preview byte decoding must stay independent of Qt and listener code."""

    source = _DECODER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_decode_preview_image_returns_rgba_payload() -> None:
    """Preview decoding should normalize image bytes to detached RGBA payloads."""

    decoded = decode_preview_image(
        _png_bytes("RGB", (2, 1), (10, 20, 30)),
    )

    assert decoded.width == 2
    assert decoded.height == 1
    assert decoded.rgba_bytes == bytes((10, 20, 30, 255, 10, 20, 30, 255))


def test_decode_preview_image_preserves_alpha_channel() -> None:
    """Preview decoding should preserve authored alpha values."""

    decoded = decode_preview_image(
        _png_bytes("RGBA", (1, 1), (10, 20, 30, 40)),
    )

    assert decoded.rgba_bytes == bytes((10, 20, 30, 40))


def test_decode_preview_image_rejects_invalid_payload() -> None:
    """Invalid preview bytes should surface Pillow decode errors to the listener."""

    with pytest.raises(UnidentifiedImageError):
        decode_preview_image(b"not an image")
