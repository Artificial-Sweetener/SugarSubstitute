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

"""Validate a cube catalog against SugarSubstitute input-asset contracts."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.input_asset_governance.cube_contracts import validate_cube_root


def main() -> int:
    """Print deterministic cube diagnostics and return a gate status."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cube_root", type=Path)
    args = parser.parse_args()
    diagnostics = validate_cube_root(args.cube_root.resolve())
    for diagnostic in diagnostics:
        print(f"{diagnostic.path}: error ASSET-CUBE: {diagnostic.message}")
    if diagnostics:
        print(f"FAILED: Found {len(diagnostics)} input-asset contract error(s).")
        return 1
    print("Input-asset cube contracts passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
