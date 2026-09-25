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

"""Parse native video-output qualification command-line options."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Return the local video, evidence, theme, and soak selections."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument(
        "--soak-seconds",
        type=float,
        default=0.0,
        help="Keep looped native playback active for this bounded duration.",
    )
    return parser.parse_args(argv)


__all__ = ["parse_arguments"]
