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

"""Import splash pose PNGs into packaged Qt resources."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path(r"E:\devprojects\SugarIcons\splash")
DEFAULT_DESTINATION_DIR = (
    REPO_ROOT / "substitute" / "presentation" / "resources" / "splash_poses"
)
DEFAULT_QRC_PATH = (
    REPO_ROOT / "substitute" / "presentation" / "resources" / "splash_poses.qrc"
)
SPLASH_POSE_SIZE = (386, 386)


def main() -> int:
    """Import source splash poses and refresh the resource manifest."""

    args = _parse_args()
    source_dir = args.source_dir.resolve()
    destination_dir = args.destination_dir.resolve()
    qrc_path = args.qrc_path.resolve()
    _validate_import_paths(
        source_dir=source_dir,
        destination_dir=destination_dir,
        qrc_path=qrc_path,
    )
    imported_names = import_splash_poses(
        source_dir=source_dir,
        destination_dir=destination_dir,
    )
    write_splash_qrc(qrc_path=qrc_path, pose_names=imported_names)
    return 0


def import_splash_poses(
    *,
    source_dir: Path,
    destination_dir: Path,
) -> tuple[str, ...]:
    """Resize source PNGs with Lanczos and write the packaged pose directory."""

    pose_paths = _discover_pose_paths(source_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    for existing_file in destination_dir.glob("*.png"):
        existing_file.unlink()

    imported_names: list[str] = []
    for source_path in pose_paths:
        destination_path = destination_dir / source_path.name
        _resize_pose(source_path=source_path, destination_path=destination_path)
        imported_names.append(source_path.name)
    return tuple(imported_names)


def write_splash_qrc(*, qrc_path: Path, pose_names: tuple[str, ...]) -> None:
    """Write the Qt resource manifest for the imported splash poses."""

    lines = [
        "<RCC>",
        '  <qresource prefix="/substitute/splash/poses">',
    ]
    for pose_name in pose_names:
        lines.append(f'    <file alias="{pose_name}">splash_poses/{pose_name}</file>')
    lines.extend(
        [
            "  </qresource>",
            "</RCC>",
            "",
        ]
    )
    qrc_path.write_text("\n".join(lines), encoding="utf-8")


def _resize_pose(*, source_path: Path, destination_path: Path) -> None:
    """Resize one source pose to the runtime target size using Pillow Lanczos."""

    with Image.open(source_path) as source_image:
        image = source_image.convert("RGBA")
        resized_image = image.resize(SPLASH_POSE_SIZE, Image.Resampling.LANCZOS)
        resized_image.save(destination_path)


def _discover_pose_paths(source_dir: Path) -> tuple[Path, ...]:
    """Return numerically sorted splash PNG paths from the source directory."""

    if not source_dir.exists():
        raise FileNotFoundError(f"Splash source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Splash source path is not a directory: {source_dir}")
    return tuple(sorted(source_dir.glob("*.png"), key=_pose_sort_key))


def _pose_sort_key(path: Path) -> tuple[int, int | str]:
    """Sort numeric filenames before named filenames without lexical mistakes."""

    stem = path.stem
    if stem.isdigit():
        return (0, int(stem))
    return (1, stem.casefold())


def _validate_import_paths(
    *,
    source_dir: Path,
    destination_dir: Path,
    qrc_path: Path,
) -> None:
    """Fail closed if destination paths do not stay inside the repository."""

    repo_root = REPO_ROOT.resolve()
    for path in (destination_dir, qrc_path.parent):
        if not path.is_relative_to(repo_root):
            raise ValueError(f"Splash import output must stay inside repo: {path}")
    if not source_dir.exists():
        raise FileNotFoundError(f"Splash source directory does not exist: {source_dir}")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the splash pose importer."""

    parser = argparse.ArgumentParser(description="Import packaged splash poses.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing source splash PNGs.",
    )
    parser.add_argument(
        "--destination-dir",
        type=Path,
        default=DEFAULT_DESTINATION_DIR,
        help="Packaged splash pose destination directory.",
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
