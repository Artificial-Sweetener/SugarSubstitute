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

"""Verify deterministic prompt-detection workflow fixtures."""

from __future__ import annotations

from pathlib import Path

from tests.headless_prompt_detection_harness import HeadlessPromptDetectionHarness
from tests.prompt_detection_fixture_catalog import (
    deterministic_prompt_detection_fixtures,
)


def test_repository_workflows_have_exact_prompt_detection() -> None:
    """Repository-owned workflows should detect prompts without false positives."""

    repository_root = Path(__file__).parents[1]
    fixtures = deterministic_prompt_detection_fixtures(repository_root)

    harness = HeadlessPromptDetectionHarness()
    report = harness.run(fixtures)
    repeated_report = harness.run(fixtures)

    assert report.succeeded, report
    assert repeated_report == report
    assert all(not fixture.unexpected for fixture in report.fixtures)
    assert all(not fixture.duplicate_order_nodes for fixture in report.fixtures)
    assert sum(len(fixture.detected) for fixture in report.fixtures) == 2
    sdxl = report.fixtures[0]
    assert sdxl.card_order[:2] == ("51", "50")
    assert sdxl.card_order.count("51") == 1
    assert sdxl.card_order.count("50") == 1
    assert report.fixtures[-1].ambiguities == (
        {
            "reason": "conflicting_roles",
            "detail": "Editable field has both positive and negative evidence.",
            "fields": ["1.text"],
        },
    )
