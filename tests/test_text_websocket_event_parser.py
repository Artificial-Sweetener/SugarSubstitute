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

"""Tests for Comfy text websocket event parsing."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from substitute.infrastructure.comfy.text_websocket_event_parser import (
    parse_text_websocket_message,
)

_PARSER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "text_websocket_event_parser.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_text_websocket_event_parser_imports_no_ui_or_listener_boundaries() -> None:
    """Text websocket parsing must stay independent of UI and listener code."""

    source = _PARSER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_parse_text_websocket_message_returns_message_type_and_data() -> None:
    """Text payload parsing should preserve the decoded message and data mapping."""

    parsed = parse_text_websocket_message(
        json.dumps(
            {
                "type": "progress",
                "data": {"prompt_id": "pid-1", "node": "1"},
                "extra": True,
            }
        )
    )

    assert parsed.message == {
        "type": "progress",
        "data": {"prompt_id": "pid-1", "node": "1"},
        "extra": True,
    }
    assert parsed.message_type == "progress"
    assert parsed.data == {"prompt_id": "pid-1", "node": "1"}


@pytest.mark.parametrize("data_value", [None, [], "bad"])
def test_parse_text_websocket_message_normalizes_non_mapping_data(
    data_value: object,
) -> None:
    """Non-object data fields should preserve the listener's empty-dict behavior."""

    parsed = parse_text_websocket_message(
        json.dumps({"type": "execution_success", "data": data_value})
    )

    assert parsed.message_type == "execution_success"
    assert parsed.data == {}


def test_parse_text_websocket_message_preserves_malformed_json_failure() -> None:
    """Malformed JSON should continue to raise the JSON decode error."""

    with pytest.raises(json.JSONDecodeError):
        parse_text_websocket_message("{not-json")
