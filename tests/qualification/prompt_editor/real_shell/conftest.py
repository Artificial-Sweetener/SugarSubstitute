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

"""Provide lifecycle-safe real-shell qualification scenarios."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


@pytest.fixture
def real_shell_scenario(tmp_path: Path) -> Iterator[PromptEditorRealShellScenario]:
    """Create and close one production-mounted prompt-editor scenario."""

    scenario = PromptEditorRealShellScenario(artifact_root=tmp_path)
    try:
        yield scenario
    finally:
        scenario.close()
