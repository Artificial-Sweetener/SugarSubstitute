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

"""Resolve finite update qualification sources from compatibility boundaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

from tools.ci.historical_release_contract import (
    HistoricalReleaseContractError,
    validated_published_at,
)
from sugarsubstitute_shared.update_compatibility import (
    UpdateCompatibilityContract,
    load_repository_update_compatibility,
)


_SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class UpgradeSourceResolutionError(RuntimeError):
    """Report an incomplete or malformed stable release history."""


def resolve_upgrade_sources(
    *,
    repository: str,
    candidate_version: str,
    selection: Literal["complete", "latest-only"] = "complete",
    fetch_releases: Callable[[str], object] | None = None,
    compatibility: UpdateCompatibilityContract | None = None,
) -> list[dict[str, str]]:
    """Return previous, oldest-direct, and declared-boundary upgrade sources."""

    payload = (fetch_releases or _fetch_github_releases)(repository)
    if not isinstance(payload, list):
        raise UpgradeSourceResolutionError("GitHub releases response must be a list.")
    candidate_tag = f"v{candidate_version}"
    stable_releases: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise UpgradeSourceResolutionError(
                "GitHub release entry must be an object."
            )
        tag = item.get("tag_name")
        if (
            item.get("draft") is False
            and item.get("prerelease") is False
            and isinstance(tag, str)
            and _SEMVER_TAG.fullmatch(tag)
            and tag != candidate_tag
        ):
            try:
                stable_releases[tag] = validated_published_at(item.get("published_at"))
            except HistoricalReleaseContractError as error:
                raise UpgradeSourceResolutionError(str(error)) from error
    stable_tags = list(stable_releases)
    stable_tags.sort(key=_version_key, reverse=True)
    if selection == "latest-only":
        if not stable_tags:
            raise UpgradeSourceResolutionError(
                "Expected at least 1 stable historical release."
            )
        return [
            {
                "published_at": stable_releases[stable_tags[0]],
                "tag": stable_tags[0],
                "version": stable_tags[0].removeprefix("v"),
                "boundary": "previous-stable",
            }
        ]
    if not stable_tags:
        raise UpgradeSourceResolutionError(
            "Expected at least 1 stable historical release."
        )
    contract = compatibility or load_repository_update_compatibility(_REPOSITORY_ROOT)
    selected: dict[str, list[str]] = {}

    def select(tag: str, boundary: str) -> None:
        """Select one tag once while retaining every represented boundary."""

        if tag not in stable_releases:
            raise UpgradeSourceResolutionError(
                f"Compatibility boundary {boundary} requires missing release {tag}."
            )
        selected.setdefault(tag, []).append(boundary)

    select(stable_tags[0], "previous-stable")
    direct_floor = _version_key(f"v{contract.minimum_direct_launcher_version}")
    direct_tags = [tag for tag in stable_tags if _version_key(tag) >= direct_floor]
    if direct_tags:
        select(direct_tags[-1], "oldest-direct")
    for version, boundary in contract.qualification_versions():
        select(f"v{version}", boundary)
    return [
        {
            "published_at": stable_releases[tag],
            "tag": tag,
            "version": tag.removeprefix("v"),
            "boundary": "+".join(selected[tag]),
        }
        for tag in selected
    ]


def _fetch_github_releases(repository: str) -> object:
    """Read stable release metadata through GitHub's authenticated REST API."""

    request = Request(  # noqa: S310
        f"https://api.github.com/repos/{repository}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"
            if os.environ.get("GITHUB_TOKEN")
            else "",
            "User-Agent": "SugarSubstitute-release-qualification",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _version_key(tag: str) -> tuple[int, int, int]:
    """Return the sortable semantic version components for one valid tag."""

    match = _SEMVER_TAG.fullmatch(tag)
    if match is None:
        raise UpgradeSourceResolutionError(f"Invalid release tag: {tag}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse release-source matrix inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument(
        "--selection",
        choices=("complete", "latest-only"),
        default="complete",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve upgrade sources and write a GitHub Actions matrix output."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    matrix = resolve_upgrade_sources(
        repository=args.repository,
        candidate_version=args.candidate_version,
        selection=args.selection,
    )
    encoded = json.dumps(matrix, separators=(",", ":"))
    output_path = args.output or (
        Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None
    )
    if output_path is None:
        print(encoded)
    else:
        with output_path.open("a", encoding="utf-8") as output:
            output.write(f"matrix={encoded}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
