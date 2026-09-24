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

"""Render deterministic full editor-panel baselines from captured Base-Cubes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.editor_panel_baseline import render_editor_panel_baseline
from tools.editor_projection_rig.scenarios import resolve_scenarios

_DEFAULT_BASE_CUBES = Path(
    r"E:\ComfyUI\custom_nodes\SugarCubes\.sugarcubes"
    r"\Artificial-Sweetener\Base-Cubes"
)
_DEFAULT_FIXTURES = Path("artifacts/editor_projection_rig/fixtures")
_DEFAULT_OUTPUT = Path("artifacts/editor-panel-baseline")


def _parse_names(value: str) -> tuple[str, ...]:
    """Return normalized comma-separated CLI values."""

    values = tuple(item.strip().casefold() for item in value.split(",") if item.strip())
    if not values:
        raise ValueError("At least one value is required.")
    return values


def main(argv: list[str] | None = None) -> int:
    """Render the requested editor-panel baseline matrix."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="both")
    parser.add_argument("--fixtures", type=Path, default=_DEFAULT_FIXTURES)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--base-cubes", type=Path, default=_DEFAULT_BASE_CUBES)
    parser.add_argument("--themes", default="light,dark")
    parser.add_argument("--positions", default="top,middle,bottom")
    args = parser.parse_args(argv)
    manifest = render_editor_panel_baseline(
        scenarios=resolve_scenarios(args.scenario),
        fixtures_dir=args.fixtures,
        output_dir=args.output,
        base_cubes_dir=args.base_cubes,
        theme_names=_parse_names(args.themes),
        position_names=_parse_names(args.positions),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
