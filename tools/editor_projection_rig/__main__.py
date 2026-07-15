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

"""Command-line entry point for the editor projection optimization rig."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capture import CaptureEndpoint, capture_scenarios
from .production_trace import trace_production_scenarios
from .replay import compare_fixture_dirs, replay_scenarios
from .report import format_json
from .scenarios import resolve_scenarios


def main(argv: list[str] | None = None) -> int:
    """Run the editor projection rig command line."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture_scenarios(
                resolve_scenarios(args.scenario),
                output_dir=Path(args.output),
                endpoint=CaptureEndpoint(base_url=args.endpoint),
            )
        elif args.command == "replay":
            result = replay_scenarios(
                resolve_scenarios(args.scenario),
                fixtures_dir=Path(args.fixtures),
                iterations=args.iterations,
                report_path=Path(args.report),
            )
        elif args.command == "compare":
            result = compare_fixture_dirs(
                expected_dir=Path(args.expected),
                actual_dir=Path(args.actual),
            )
        elif args.command == "trace":
            result = trace_production_scenarios(
                resolve_scenarios(args.scenario),
                fixtures_dir=Path(args.fixtures),
                iterations=args.iterations,
                report_path=Path(args.report),
                settle_turns=args.settle_turns,
                write_production_targets=args.write_production_targets,
                alternating=args.scenario.casefold() == "alternating",
            )
        else:
            parser.print_help()
            return 2
    except Exception as error:
        sys.stderr.write(f"editor_projection_rig failed: {error!r}\n")
        return 1
    sys.stdout.write(format_json(result))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="python -m tools.editor_projection_rig",
        description="Capture and replay editor projection optimization fixtures.",
    )
    subparsers = parser.add_subparsers(dest="command")
    capture = subparsers.add_parser("capture", help="Capture live workflow fixtures.")
    capture.add_argument("--scenario", default="both")
    capture.add_argument(
        "--output",
        default="artifacts/editor_projection_rig/fixtures",
    )
    capture.add_argument("--endpoint", default="http://127.0.0.1:8188")
    replay = subparsers.add_parser("replay", help="Replay captured fixtures.")
    replay.add_argument("--scenario", default="both")
    replay.add_argument("--iterations", type=int, default=5)
    replay.add_argument(
        "--fixtures",
        default="artifacts/editor_projection_rig/fixtures",
    )
    replay.add_argument(
        "--report",
        default="artifacts/editor_projection_rig/reports/latest-report.json",
    )
    compare = subparsers.add_parser("compare", help="Compare two fixture directories.")
    compare.add_argument("--expected", required=True)
    compare.add_argument("--actual", required=True)
    trace = subparsers.add_parser(
        "trace",
        help="Run offscreen production-path projection traces.",
    )
    trace.add_argument("--scenario", default="both")
    trace.add_argument("--iterations", type=int, default=3)
    trace.add_argument(
        "--fixtures",
        default="artifacts/editor_projection_rig/fixtures",
    )
    trace.add_argument(
        "--report",
        default="artifacts/editor_projection_rig/reports/production-trace.json",
    )
    trace.add_argument("--settle-turns", type=int, default=500)
    trace.add_argument("--write-production-targets", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
