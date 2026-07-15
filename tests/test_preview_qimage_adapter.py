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

"""Tests for Qt preview QImage adapter behavior."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, cast

import pytest
from substitute.infrastructure.comfy.preview_image_decoder import DecodedPreviewImage
from substitute.presentation.qt import preview_qimage_adapter

_ADAPTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "presentation"
    / "qt"
    / "preview_qimage_adapter.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _FakeQImage:
    """Record constructor arguments for adapter tests."""

    created: ClassVar[list["_FakeQImage"]] = []
    Format: ClassVar[object | None] = SimpleNamespace(Format_RGBA8888="nested-rgba")

    def __init__(self, *args: object) -> None:
        self.args = args
        type(self).created.append(self)

    def copy(self) -> "_FakeQImage":
        """Return the copied image result."""

        return self


class _FallbackQImage(_FakeQImage):
    """Record constructor arguments for older direct-format Qt stubs."""

    Format = None
    Format_RGBA8888 = "fallback-rgba"


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_preview_qimage_adapter_imports_no_listener_or_widget_boundaries() -> None:
    """Qt adapter must not import listener orchestration or widget libraries."""

    source = _ADAPTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_preview_image_to_qimage_uses_pyside_format_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QImage conversion should use the PySide6 enum-style RGBA format."""

    _FakeQImage.created = []
    monkeypatch.setattr(preview_qimage_adapter, "QImage", _FakeQImage)

    result = cast(
        _FakeQImage,
        preview_qimage_adapter.preview_image_to_qimage(
            DecodedPreviewImage(
                rgba_bytes=b"rgba",
                width=2,
                height=1,
            )
        ),
    )

    assert result is _FakeQImage.created[0]
    assert result.args == (b"rgba", 2, 1, "nested-rgba")


def test_preview_image_to_qimage_supports_direct_format_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QImage conversion should support direct Format_RGBA8888 test doubles."""

    _FallbackQImage.created = []
    monkeypatch.setattr(preview_qimage_adapter, "QImage", _FallbackQImage)

    result = cast(
        _FallbackQImage,
        preview_qimage_adapter.preview_image_to_qimage(
            DecodedPreviewImage(
                rgba_bytes=b"rgba",
                width=2,
                height=1,
            )
        ),
    )

    assert result is _FallbackQImage.created[0]
    assert result.args == (b"rgba", 2, 1, "fallback-rgba")
