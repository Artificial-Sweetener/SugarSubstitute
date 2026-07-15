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

"""Provide shared terminal-style Qt output widgets for launcher and app UIs."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sugarsubstitute_shared.presentation.terminal.output_stream import (
        TerminalOutputStream,
    )
    from sugarsubstitute_shared.presentation.terminal.output_transcript import (
        TerminalOutputMutation,
        TerminalOutputMutationKind,
        TerminalOutputTranscript,
    )
    from sugarsubstitute_shared.presentation.terminal.output_view import (
        TerminalOutputView,
    )

_LAZY_EXPORTS = {
    "TerminalOutputMutation": (
        "sugarsubstitute_shared.presentation.terminal.output_transcript"
    ),
    "TerminalOutputMutationKind": (
        "sugarsubstitute_shared.presentation.terminal.output_transcript"
    ),
    "TerminalOutputStream": "sugarsubstitute_shared.presentation.terminal.output_stream",
    "TerminalOutputTranscript": (
        "sugarsubstitute_shared.presentation.terminal.output_transcript"
    ),
    "TerminalOutputView": "sugarsubstitute_shared.presentation.terminal.output_view",
}

__all__ = [
    "TerminalOutputMutation",
    "TerminalOutputMutationKind",
    "TerminalOutputStream",
    "TerminalOutputTranscript",
    "TerminalOutputView",
]


def __getattr__(name: str) -> object:
    """Resolve shared terminal exports without importing widget code eagerly."""

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
