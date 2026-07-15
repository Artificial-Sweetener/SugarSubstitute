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

"""Run named onboarding automation scenarios and emit structured results."""

from __future__ import annotations

import argparse
import sys

from tests.onboarding_automation.driver import OnboardingAutomationDriver
from tests.onboarding_automation.fixture_paths import resolve_scenario_paths
from tests.onboarding_automation.scenarios import build_scenarios
from tests.onboarding_automation.screenshot_capture import (
    prepare_screenshot_directory,
)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the onboarding scenario runner."""

    parser = argparse.ArgumentParser(
        description="Drive the onboarding window through a named automation scenario.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario name to execute.",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one named onboarding automation scenario."""

    parser = build_argument_parser()
    args = parser.parse_args(argv)
    paths = resolve_scenario_paths()
    scenarios = build_scenarios(paths)
    if args.list_scenarios:
        for listed_scenario in scenarios.values():
            print(f"{listed_scenario.name}: {listed_scenario.description}")
        return 0
    scenario = scenarios.get(args.scenario)
    if scenario is None:
        parser.error(f"Unknown scenario: {args.scenario}")
        return 2
    assert scenario is not None
    screenshot_dir = prepare_screenshot_directory(paths.artifact_root, scenario.name)
    result = OnboardingAutomationDriver(
        scenario=scenario,
        screenshot_dir=screenshot_dir,
    ).run()
    print(result.to_json())
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
