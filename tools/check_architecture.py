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

"""Check repository architecture governance."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.architecture_governance.validation import validate_repository


def main(argv: Sequence[str] | None = None) -> int:
    """Validate current architecture state."""

    if argv:
        raise ValueError("The architecture checker accepts no arguments")
    root = Path(__file__).resolve().parents[1]
    diagnostics = validate_repository(root)
    for diagnostic in diagnostics:
        print(diagnostic.render())
    errors = [item for item in diagnostics if item.severity == "error"]
    if errors:
        print(f"FAILED: Found {len(errors)} architecture governance errors.")
        return 1
    warning_count = len(diagnostics)
    print(f"SUCCESS: Architecture is valid ({warning_count} structural warnings).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
