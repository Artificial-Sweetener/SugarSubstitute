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

"""Provide immutable shared fixtures for direct-workflow qualification."""

from __future__ import annotations

from pathlib import Path

from tests.support.node_behavior.prompt_detection_fixtures import (
    PromptDetectionFixture,
    deterministic_prompt_detection_fixtures,
)


def deterministic_sdxl_fixture() -> PromptDetectionFixture:
    """Return the repository-owned SDXL projection fixture."""

    repository_root = Path(__file__).parents[5]
    return deterministic_prompt_detection_fixtures(repository_root)[0]
