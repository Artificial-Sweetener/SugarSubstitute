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

"""Provide the command-line interface for release-asset assembly."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from launcher.sugarsubstitute_launcher.platforms import (
    InstallerFormat,
    launcher_target_for_key,
)
from tools.release_assets.assembly import build_local_release_channel
from tools.release_assets.launcher_archive import build_installed_launcher_zip
from tools.release_assets.models import NativeInstallerInput, PlatformReleaseInput
from tools.release_assets.payload import inspect_payload_zip


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE_CHANNEL_DIR = REPO_ROOT / ".local-release-channel"


def main() -> int:
    """Run the selected release-asset command."""

    args = parse_args()
    if args.command == "inspect":
        for archive_name in inspect_payload_zip(args.zip_path):
            print(archive_name)
        return 0
    if args.command == "package-launcher":
        output_path = build_installed_launcher_zip(
            launcher_bundle_dir=args.bundle_dir,
            output_path=args.output_path,
            target=launcher_target_for_key(args.target),
        )
        print(output_path)
        return 0
    result = build_local_release_channel(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        version=args.version,
        channel=args.channel,
        minimum_launcher_version=args.minimum_launcher_version,
        platform_inputs=platform_inputs_from_args(args),
        asset_base_url=args.asset_base_url,
    )
    print(f"app_zip={result.app_zip_path}")
    print(f"manifest={result.manifest_path}")
    print(f"checksums={result.checksums_path}")
    return 0


def parse_args() -> argparse.Namespace:
    """Parse release-asset command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Build SugarSubstitute release-channel assets.",
    )
    subparsers = parser.add_subparsers(dest="command")
    build_parser = subparsers.add_parser(
        "build",
        help="Build the app payload, native assets, manifest, and checksums.",
    )
    build_parser.add_argument("--version", required=True)
    build_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RELEASE_CHANNEL_DIR,
    )
    build_parser.add_argument("--channel", default="stable")
    build_parser.add_argument("--minimum-launcher-version", default="0.1.0")
    build_parser.add_argument(
        "--platform-input",
        action="append",
        default=[],
        nargs=2,
        metavar=("TARGET", "LAUNCHER_BUNDLE"),
    )
    build_parser.add_argument(
        "--installer-input",
        action="append",
        default=[],
        nargs=3,
        metavar=("TARGET", "FORMAT", "INSTALLER"),
    )
    build_parser.add_argument("--asset-base-url", default=None)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("zip_path", type=Path)
    package_parser = subparsers.add_parser("package-launcher")
    package_parser.add_argument("--target", required=True)
    package_parser.add_argument("--bundle-dir", type=Path, required=True)
    package_parser.add_argument("--output-path", type=Path, required=True)
    parser.set_defaults(command="build")
    return parser.parse_args()


def platform_inputs_from_args(
    args: argparse.Namespace,
) -> tuple[PlatformReleaseInput, ...]:
    """Join launcher and installer CLI inputs by target key."""

    installers_by_target: dict[str, list[NativeInstallerInput]] = defaultdict(list)
    for target_key, format_name, source_path in args.installer_input:
        installers_by_target[str(target_key)].append(
            NativeInstallerInput(
                format=InstallerFormat(str(format_name)),
                source_path=Path(str(source_path)),
            )
        )
    platform_inputs = []
    for target_key, launcher_source in args.platform_input:
        normalized_target_key = str(target_key)
        platform_inputs.append(
            PlatformReleaseInput(
                target=launcher_target_for_key(normalized_target_key),
                launcher_source=Path(str(launcher_source)),
                installers=tuple(installers_by_target.pop(normalized_target_key, ())),
            )
        )
    if installers_by_target:
        raise ValueError(
            "Installer inputs have no matching platform input: "
            f"{sorted(installers_by_target)}"
        )
    return tuple(platform_inputs)
