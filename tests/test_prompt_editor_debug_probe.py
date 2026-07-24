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

"""Verify prompt-editor diagnostics stay outside disabled hot paths."""

from __future__ import annotations

import logging

from substitute.presentation.editor.prompt_editor.debug_probe import (
    autocomplete_probe_state,
    log_prompt_editor_probe,
    surface_probe_state,
)

_PROBE_LOGGER_NAME = "sugarsubstitute.presentation.editor.prompt_editor.debug_probe"


class _FailOnInspection:
    """Fail if disabled diagnostics inspect any owner state."""

    def __getattribute__(self, name: str) -> object:
        """Reject every attempted diagnostic attribute read."""

        raise AssertionError(f"Disabled probe inspected {name}.")


def test_disabled_probe_performs_no_owner_state_work() -> None:
    """Keep diagnostic traversal, snapshots, and serialization off hot paths."""

    logger = logging.getLogger(_PROBE_LOGGER_NAME)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        target = _FailOnInspection()

        assert surface_probe_state(target) == {}
        assert autocomplete_probe_state(target) == {}
        log_prompt_editor_probe("disabled", target=target)
    finally:
        logger.setLevel(previous_level)
