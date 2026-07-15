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

"""Measure prompt editor hot-path responsiveness with deterministic scenarios."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from substitute.devtools.prompt_editor_performance.qt_app import (
    prompt_performance_application,
)
from substitute.devtools.prompt_editor_performance.reporting import (
    print_results as _print_results,
)
from substitute.devtools.prompt_editor_performance.runner import (
    run_scenarios as _run_scenarios,
)
from substitute.devtools.prompt_editor_performance.scenarios import (
    scenarios as _scenarios,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run prompt editor responsiveness scenarios and print a compact table."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--typed-text",
        default="blue hair, looking at viewer, cinematic light",
        help="Text inserted into typing scenarios. The value is never printed.",
    )
    parser.add_argument(
        "--disable-logging",
        action="store_true",
        help="Disable Python logging while measuring keypress costs.",
    )
    args = parser.parse_args(argv)

    if args.disable_logging:
        logging.disable(logging.CRITICAL)

    app = prompt_performance_application()
    scenarios = _scenarios(args.typed_text)
    results = _run_scenarios(app, scenarios)
    _print_results(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
