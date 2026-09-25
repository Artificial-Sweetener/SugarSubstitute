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

"""Render deterministic professional-motion evidence from Base-Cubes fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.editor_panel_motion import render_editor_panel_motion

_DEFAULT_FIXTURE = Path(
    "artifacts/editor_projection_rig/fixtures/workflow_sdxl_baseline.json"
)
_DEFAULT_OUTPUT = Path("artifacts/editor-panel-motion")


def main(argv: list[str] | None = None) -> int:
    """Render offscreen insertion, reorder, and removal motion frames."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--base-cubes", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = render_editor_panel_motion(
        fixture_path=args.fixture,
        output_dir=args.output,
        base_cubes_dir=args.base_cubes,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
