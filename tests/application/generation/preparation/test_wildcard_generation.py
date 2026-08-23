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

"""Run the production generation-path wildcard seed harness."""

from __future__ import annotations

from pathlib import Path

from tests.application.generation.preparation.wildcard_fixture_harness import (
    HeadlessWildcardGenerationHarness,
)


def test_workflow_seeds_change_production_wildcard_resolution(tmp_path: Path) -> None:
    """Different randomized global seeds should prepare different candidates."""

    report = HeadlessWildcardGenerationHarness(tmp_path).run()

    assert report.passed, report.failure_summary()
    assert [observation.effective_seed for observation in report.observations] == [
        1,
        5,
    ]
    assert [observation.prepared_prompt for observation in report.observations] == [
        "portrait first",
        "portrait third",
    ]
