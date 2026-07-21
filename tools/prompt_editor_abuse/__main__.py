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

"""Run production-mounted prompt-editor abuse and performance campaigns."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .campaign import run_campaign
from .comparison import compare_report_files, format_comparison, write_comparison
from .minimization import minimized_scenario_from_report
from .models import PromptAbuseScenario
from .replay import load_report_scenarios, scenario_prefix
from .reporting import format_summary, write_report
from .workloads import resolve_scenarios


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command arguments and run one headless campaign."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("run", "diagnose", "replay", "minimize", "compare"),
    )
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--frame-budget-ms", type=float, default=16.667)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/prompt_editor_abuse/latest.json"),
    )
    parser.add_argument(
        "--structural-probe",
        action="store_true",
        help="collect external per-action owner counts; timings are diagnostic only",
    )
    parser.add_argument(
        "--enforce-structural",
        action="store_true",
        help="enforce portable owner-work budgets",
    )
    parser.add_argument(
        "--enforce-reference-timing",
        action="store_true",
        help=(
            "enforce the frame target on designated reference hardware; "
            "contended timing evidence fails"
        ),
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--action-limit", type=int)
    parser.add_argument("--threshold-ms", type=float)
    args = parser.parse_args(list(argv) if argv is not None else None)
    structural_probe = args.structural_probe or args.enforce_structural
    if structural_probe and args.enforce_reference_timing:
        parser.error(
            "reference timing cannot be enforced in an instrumented structural run"
        )
    if args.command == "compare":
        if args.baseline is None or args.candidate is None:
            parser.error("compare requires --baseline and --candidate")
        comparison = compare_report_files(args.baseline, args.candidate)
        write_comparison(comparison, args.output)
        print(format_comparison(comparison))
        return 1 if comparison.correctness_regressed else 0
    scenarios: tuple[PromptAbuseScenario, ...]
    if args.command == "minimize":
        if args.input is None:
            parser.error("minimize requires --input")
        if args.scenario == "all":
            parser.error("minimize requires one exact --scenario")
        scenarios = (
            minimized_scenario_from_report(
                args.input,
                scenario_name=args.scenario,
                threshold_ms=args.threshold_ms,
            ),
        )
    elif args.command == "replay":
        if args.input is None:
            parser.error("replay requires --input")
        scenarios = load_report_scenarios(
            args.input,
            scenario_name=args.scenario,
        )
    else:
        scenarios = resolve_scenarios(args.scenario, seed=args.seed)
    if args.action_limit is not None:
        scenarios = tuple(
            scenario_prefix(scenario, action_count=args.action_limit)
            for scenario in scenarios
        )
    report = run_campaign(
        scenarios,
        repetitions=args.repetitions,
        seed=args.seed,
        frame_budget_ms=args.frame_budget_ms,
        artifact_root=args.output.parent,
        deep_trace=args.command == "diagnose",
        structural_probe=structural_probe,
    )
    write_report(report, args.output)
    print(format_summary(report))
    if not report.correctness_passed:
        return 1
    if args.enforce_structural and not report.structural_performance_passed:
        return 1
    if args.enforce_reference_timing and (
        not report.timing_evidence_representative or not report.timing_target_passed
    ):
        return 1
    if (
        (args.enforce_structural or args.enforce_reference_timing)
        and args.scenario.casefold() == "all"
        and report.missing_operations
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
