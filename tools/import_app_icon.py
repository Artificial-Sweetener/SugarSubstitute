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

"""Import the project app icon and generate deterministic runtime assets."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_PATH = Path(r"E:\devprojects\sugaricons\icon.png")
DEFAULT_DESTINATION_DIR = (
    REPO_ROOT / "substitute" / "presentation" / "resources" / "app_icons"
)
DEFAULT_QRC_PATH = (
    REPO_ROOT / "substitute" / "presentation" / "resources" / "app_icons.qrc"
)
SOURCE_IMAGE_NAME = "source.png"
APP_ICON_PNG_SIZES: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 128, 256)
APP_ICON_ICO_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
APP_ICON_RESOURCE_PREFIX = "/substitute/app/icon"


def main() -> int:
    """Import the configured app icon source into repository runtime assets."""

    args = _parse_args()
    source_path = args.source_path.resolve()
    destination_dir = args.destination_dir.resolve()
    qrc_path = args.qrc_path.resolve()
    _validate_import_paths(
        source_path=source_path,
        destination_dir=destination_dir,
        qrc_path=qrc_path,
    )
    import_app_icon(
        source_path=source_path,
        destination_dir=destination_dir,
        qrc_path=qrc_path,
    )
    return 0


def import_app_icon(
    *,
    source_path: Path,
    destination_dir: Path,
    qrc_path: Path,
) -> None:
    """Generate app icon runtime assets from one high-resolution source image."""

    destination_dir.mkdir(parents=True, exist_ok=True)
    qrc_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as source_image:
        image = source_image.convert("RGBA")
        _validate_source_image(image=image, source_path=source_path)
        _copy_source_image(source_path=source_path, destination_dir=destination_dir)
        _write_png_sizes(image=image, destination_dir=destination_dir)
        _write_ico(image=image, destination_dir=destination_dir)
    write_app_icon_qrc(qrc_path=qrc_path)


def write_app_icon_qrc(*, qrc_path: Path) -> None:
    """Write the Qt resource manifest for generated app icon PNG sizes."""

    lines = [
        "<RCC>",
        f'  <qresource prefix="{APP_ICON_RESOURCE_PREFIX}">',
    ]
    for size in APP_ICON_PNG_SIZES:
        file_name = _png_file_name(size)
        lines.append(f'    <file alias="{size}.png">app_icons/{file_name}</file>')
    lines.extend(
        [
            "  </qresource>",
            "</RCC>",
            "",
        ]
    )
    qrc_path.write_text("\n".join(lines), encoding="utf-8")


def _copy_source_image(*, source_path: Path, destination_dir: Path) -> None:
    """Copy the high-resolution source image into the repository asset folder."""

    destination_path = destination_dir / SOURCE_IMAGE_NAME
    if source_path == destination_path:
        return
    shutil.copyfile(source_path, destination_path)


def _write_png_sizes(*, image: Image.Image, destination_dir: Path) -> None:
    """Write deterministic Lanczos-resampled PNG assets for all runtime sizes."""

    for size in APP_ICON_PNG_SIZES:
        destination_path = destination_dir / _png_file_name(size)
        resized_image = image.resize((size, size), Image.Resampling.LANCZOS)
        resized_image.save(destination_path)


def _write_ico(*, image: Image.Image, destination_dir: Path) -> None:
    """Write a multi-size Windows icon using Pillow's Lanczos ICO generation."""

    icon_path = destination_dir / "app_icon.ico"
    image.save(
        icon_path,
        format="ICO",
        sizes=tuple((size, size) for size in APP_ICON_ICO_SIZES),
    )


def _validate_source_image(*, image: Image.Image, source_path: Path) -> None:
    """Reject source images that cannot produce square app icon assets."""

    width, height = image.size
    if width != height:
        raise ValueError(f"App icon source must be square: {source_path}")


def _validate_import_paths(
    *,
    source_path: Path,
    destination_dir: Path,
    qrc_path: Path,
) -> None:
    """Fail closed when outputs would escape the repository."""

    repo_root = REPO_ROOT.resolve()
    for output_path in (destination_dir, qrc_path.parent):
        if not output_path.is_relative_to(repo_root):
            raise ValueError(f"App icon output must stay inside repo: {output_path}")
    if not source_path.exists():
        raise FileNotFoundError(f"App icon source does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"App icon source is not a file: {source_path}")


def _png_file_name(size: int) -> str:
    """Return the generated PNG file name for one square icon size."""

    return f"app_icon_{size}.png"


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for importing the app icon."""

    parser = argparse.ArgumentParser(description="Import the app icon assets.")
    parser.add_argument(
        "--source-path",
        type=Path,
        default=DEFAULT_SOURCE_PATH,
        help="High-resolution source PNG to adopt as the project icon.",
    )
    parser.add_argument(
        "--destination-dir",
        type=Path,
        default=DEFAULT_DESTINATION_DIR,
        help="Repository destination directory for app icon assets.",
    )
    parser.add_argument(
        "--qrc-path",
        type=Path,
        default=DEFAULT_QRC_PATH,
        help="Qt resource manifest path to refresh.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
