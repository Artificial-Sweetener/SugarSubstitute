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

"""Populate CI's checksum-addressed managed-Comfy artifact cache."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Protocol


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from substitute.infrastructure.comfy.standalone_environment.catalog import (  # noqa: E402
    StandaloneEnvironmentCatalog,
)
from substitute.infrastructure.comfy.standalone_environment.downloader import (  # noqa: E402
    DownloadProgressCallback,
    StandaloneArtifactDownloader,
)
from substitute.infrastructure.comfy.standalone_environment.models import (  # noqa: E402
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.pinned_catalog import (  # noqa: E402
    PinnedStandaloneEnvironmentCatalog,
)


class StandaloneArtifactCacheDownloader(Protocol):
    """Acquire exact standalone artifacts into a caller-owned cache root."""

    def download(
        self,
        release: StandaloneEnvironmentRelease,
        cache_root: Path,
        *,
        on_progress: DownloadProgressCallback | None = None,
    ) -> tuple[Path, ...]:
        """Download or verify every artifact belonging to one release."""


def cache_pinned_managed_comfy_artifacts(
    *,
    cache_root: Path,
    variant: StandaloneVariantId,
    catalog: StandaloneEnvironmentCatalog | None = None,
    downloader: StandaloneArtifactCacheDownloader | None = None,
    output: Callable[[str], None] = print,
) -> tuple[Path, ...]:
    """Populate and verify one exact standalone artifact cache generation."""

    release = (catalog or PinnedStandaloneEnvironmentCatalog.load_default()).resolve(
        variant
    )
    output(
        "MANAGED_COMFY_CACHE start "
        f"variant={variant.value} release={release.release_tag} "
        f"bytes={release.total_size_bytes}"
    )
    reporter = _ProgressReporter(total_bytes=release.total_size_bytes, output=output)
    artifacts = (downloader or StandaloneArtifactDownloader()).download(
        release,
        cache_root,
        on_progress=reporter.publish,
    )
    output(
        "MANAGED_COMFY_CACHE ready "
        f"variant={variant.value} artifacts={len(artifacts)} "
        f"bytes={release.total_size_bytes}"
    )
    return artifacts


@dataclass(slots=True)
class _ProgressReporter:
    """Publish bounded five-percent artifact acquisition progress."""

    total_bytes: int
    output: Callable[[str], None]
    last_percentage: int = -5

    def publish(self, completed_bytes: int, _reported_total_bytes: int) -> None:
        """Emit increasing five-percent milestones and final completion."""

        percentage = (
            100
            if self.total_bytes <= 0
            else min(100, int(completed_bytes * 100 / self.total_bytes))
        )
        milestone = percentage - (percentage % 5)
        if milestone <= self.last_percentage:
            return
        self.last_percentage = max(self.last_percentage, milestone)
        self.output(
            "MANAGED_COMFY_CACHE progress "
            f"completed={completed_bytes} total={self.total_bytes} "
            f"percentage={percentage}"
        )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse one checksum-addressed artifact cache request."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=tuple(variant.value for variant in StandaloneVariantId),
        required=True,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Populate the requested standalone artifact cache generation."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    cache_pinned_managed_comfy_artifacts(
        cache_root=args.cache_root,
        variant=StandaloneVariantId(args.variant),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
