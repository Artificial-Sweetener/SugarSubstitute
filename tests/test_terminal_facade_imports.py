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

"""Tests for shared terminal package import boundaries."""

from __future__ import annotations

import importlib
import sys


def test_terminal_stream_import_does_not_import_output_view() -> None:
    """Importing the stream should not import the widget view facade."""

    for module_name in tuple(sys.modules):
        if module_name.startswith("sugarsubstitute_shared.presentation.terminal"):
            sys.modules.pop(module_name, None)

    module = importlib.import_module(
        "sugarsubstitute_shared.presentation.terminal.output_stream"
    )

    assert module.TerminalOutputStream.__name__ == "TerminalOutputStream"
    assert "sugarsubstitute_shared.presentation.terminal.output_view" not in sys.modules


def test_terminal_facade_resolves_output_view_lazily() -> None:
    """The package facade should still expose the terminal view on demand."""

    for module_name in tuple(sys.modules):
        if module_name.startswith("sugarsubstitute_shared.presentation.terminal"):
            sys.modules.pop(module_name, None)

    facade = importlib.import_module("sugarsubstitute_shared.presentation.terminal")

    assert facade.TerminalOutputStream.__name__ == "TerminalOutputStream"
    assert "sugarsubstitute_shared.presentation.terminal.output_view" not in sys.modules
    assert facade.TerminalOutputView.__name__ == "TerminalOutputView"
    assert "sugarsubstitute_shared.presentation.terminal.output_view" in sys.modules
