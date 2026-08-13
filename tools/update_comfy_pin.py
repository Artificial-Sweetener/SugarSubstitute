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

"""Propose the current live Comfy standalone catalog as a reviewable pin."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from substitute.infrastructure.comfy.standalone_environment.catalog import (  # noqa: E402
    StandaloneEnvironmentCatalog,
)
from substitute.infrastructure.comfy.standalone_environment.catalog_client import (  # noqa: E402
    LiveStandaloneEnvironmentCatalogClient,
)
from substitute.infrastructure.comfy.standalone_environment.models import (  # noqa: E402
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.pinned_catalog import (  # noqa: E402
    DEFAULT_PIN_PATH,
    PinnedStandaloneEnvironmentCatalog,
    write_pinned_catalog,
)


@dataclass(frozen=True, slots=True)
class ComfyPinUpdateResult:
    """Describe one complete comparison between pinned and live metadata."""

    changed: bool
    previous_release_tags: tuple[str, ...]
    proposed_release_tags: tuple[str, ...]
    proposed_comfyui_versions: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        """Return stable machine-readable workflow output."""

        return {
            "changed": self.changed,
            "previous_release_tags": self.previous_release_tags,
            "proposed_comfyui_versions": self.proposed_comfyui_versions,
            "proposed_release_tags": self.proposed_release_tags,
        }


def update_comfy_pin(
    *,
    pin_path: Path,
    live_catalog: StandaloneEnvironmentCatalog,
) -> ComfyPinUpdateResult:
    """Write the complete live catalog only when it differs from the pin."""

    pinned_catalog = PinnedStandaloneEnvironmentCatalog.load(pin_path)
    pinned_releases = tuple(
        pinned_catalog.resolve(variant) for variant in StandaloneVariantId
    )
    proposed_releases = tuple(
        live_catalog.resolve(variant) for variant in StandaloneVariantId
    )
    proposed_catalog = PinnedStandaloneEnvironmentCatalog(
        {release.variant: release for release in proposed_releases}
    )
    changed = proposed_catalog.to_json() != pinned_catalog.to_json()
    if changed:
        write_pinned_catalog(pin_path, proposed_releases)
    return ComfyPinUpdateResult(
        changed=changed,
        previous_release_tags=_release_values(pinned_releases, "release_tag"),
        proposed_release_tags=_release_values(proposed_releases, "release_tag"),
        proposed_comfyui_versions=_release_values(proposed_releases, "comfyui_version"),
    )


def _release_values(
    releases: Sequence[StandaloneEnvironmentRelease],
    attribute: str,
) -> tuple[str, ...]:
    """Return sorted unique safe metadata values for workflow presentation."""

    values = tuple(sorted({str(getattr(release, attribute)) for release in releases}))
    if any("\n" in value or "\r" in value for value in values):
        raise ValueError(f"Comfy release metadata contains a newline: {attribute}")
    return values


def _write_github_outputs(result: ComfyPinUpdateResult) -> None:
    """Expose bounded values to the surrounding GitHub Actions step."""

    output_value = os.environ.get("GITHUB_OUTPUT")
    if not output_value:
        return
    output_path = Path(output_value)
    with output_path.open("a", encoding="utf-8") as output:
        output.write(f"changed={str(result.changed).lower()}\n")
        output.write(
            f"previous_release_tags={', '.join(result.previous_release_tags)}\n"
        )
        output.write(
            f"proposed_release_tags={', '.join(result.proposed_release_tags)}\n"
        )
        output.write(
            f"proposed_comfyui_versions={', '.join(result.proposed_comfyui_versions)}\n"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve live metadata, update the pin, and report whether it changed."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin-path", type=Path, default=DEFAULT_PIN_PATH)
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = update_comfy_pin(
        pin_path=args.pin_path,
        live_catalog=LiveStandaloneEnvironmentCatalogClient(),
    )
    _write_github_outputs(result)
    print(json.dumps(result.to_json(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
