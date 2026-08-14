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

"""Resolve the latest three stable upgrade sources plus the fixed canary."""

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


_CANARY_TAG = "v0.12.2"
_RELEASE_COUNT = 3
_SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class UpgradeSourceResolutionError(RuntimeError):
    """Report an incomplete or malformed stable release history."""


def resolve_upgrade_sources(
    *,
    repository: str,
    candidate_version: str,
    selection: Literal["complete", "latest-only"] = "complete",
    fetch_releases: Callable[[str], object] | None = None,
) -> list[dict[str, str]]:
    """Return the complete matrix or one latest focused-remediation source."""

    payload = (fetch_releases or _fetch_github_releases)(repository)
    if not isinstance(payload, list):
        raise UpgradeSourceResolutionError("GitHub releases response must be a list.")
    candidate_tag = f"v{candidate_version}"
    stable_tags: list[str] = []
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
            stable_tags.append(tag)
    stable_tags.sort(key=_version_key, reverse=True)
    if selection == "latest-only":
        if not stable_tags:
            raise UpgradeSourceResolutionError(
                "Expected at least 1 stable historical release."
            )
        return [
            {
                "tag": stable_tags[0],
                "version": stable_tags[0].removeprefix("v"),
            }
        ]
    selected = stable_tags[:_RELEASE_COUNT]
    if len(selected) != _RELEASE_COUNT:
        raise UpgradeSourceResolutionError(
            f"Expected at least {_RELEASE_COUNT} stable historical releases."
        )
    if _CANARY_TAG not in selected:
        selected.append(_CANARY_TAG)
    return [
        {
            "tag": tag,
            "version": tag.removeprefix("v"),
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
