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

"""Build the native macOS ICNS asset from the canonical application icon."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import subprocess
import tempfile


class MacosIconBuildError(RuntimeError):
    """Report invalid icon inputs or native conversion failures."""


_ICON_RENDITIONS = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)


def build_macos_icon(*, source_path: Path, output_path: Path) -> Path:
    """Convert one source PNG into a complete native ICNS iconset."""

    if platform.system() != "Darwin":
        raise MacosIconBuildError("ICNS conversion must run on macOS.")
    resolved_source = source_path.expanduser().resolve()
    resolved_output = output_path.expanduser().resolve()
    if not resolved_source.is_file():
        raise MacosIconBuildError(f"Source icon is missing: {resolved_source}")
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sugarsubstitute-icon-") as temporary:
        iconset = Path(temporary) / "SugarSubstitute.iconset"
        iconset.mkdir()
        for pixels, filename in _ICON_RENDITIONS:
            _run(
                [
                    "sips",
                    "--resampleHeightWidth",
                    str(pixels),
                    str(pixels),
                    str(resolved_source),
                    "--out",
                    str(iconset / filename),
                ]
            )
        _run(
            [
                "iconutil",
                "--convert",
                "icns",
                str(iconset),
                "--output",
                str(resolved_output),
            ]
        )
    if not resolved_output.is_file():
        raise MacosIconBuildError(f"ICNS output was not created: {resolved_output}")
    return resolved_output


def _run(command: list[str]) -> None:
    """Run one bounded native icon conversion command."""

    try:
        subprocess.run(command, check=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise MacosIconBuildError(
            f"macOS icon conversion failed: {' '.join(command)}: {error}"
        ) from error


def main() -> int:
    """Run the macOS icon builder command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_macos_icon(source_path=args.source, output_path=args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
