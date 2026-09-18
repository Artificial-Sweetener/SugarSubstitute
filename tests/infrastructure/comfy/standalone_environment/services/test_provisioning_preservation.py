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

"""Preserve workspace data and recovery inputs when standalone provisioning fails."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from collections.abc import Sequence

import pytest

from substitute.infrastructure.comfy.standalone_environment.downloader import (
    DownloadProgressCallback,
    StandaloneArtifactDownloader,
)
from substitute.infrastructure.comfy.standalone_environment.extractor import (
    StandaloneEnvironmentExtractor,
)
from substitute.infrastructure.comfy.standalone_environment.extraction_process import (
    SevenZipProgressCallback,
)
from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArtifactError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)
from substitute.infrastructure.comfy.standalone_environment.provisioner import (
    StandaloneEnvironmentProvisioner,
)
from substitute.infrastructure.comfy.standalone_environment.hydration_state import (
    StandaloneHydrationState,
)

from .support import _release_for_variant


class _Catalog:
    """Provide one immutable test release without remote catalog access."""

    def resolve(self, variant: StandaloneVariantId) -> StandaloneEnvironmentRelease:
        """Return release identity used by the real promotion owner."""

        return _release_for_variant(variant)


def _archive_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace network and archive extraction while retaining real promotion."""

    def download(
        self: StandaloneArtifactDownloader,
        release: StandaloneEnvironmentRelease,
        cache_root: Path,
        *,
        on_progress: DownloadProgressCallback | None = None,
    ) -> tuple[Path, ...]:
        """Avoid network I/O for the deterministic extraction boundary."""

        return ()

    def extract(
        self: StandaloneEnvironmentExtractor,
        release: StandaloneEnvironmentRelease,
        artifact_paths: tuple[Path, ...],
        destination: Path,
        *,
        on_extraction_progress: SevenZipProgressCallback | None = None,
    ) -> Path:
        """Materialize a valid Windows bundle without executing its fake tools."""

        (destination / "ComfyUI").mkdir(parents=True)
        (destination / "ComfyUI" / "main.py").write_text("main", encoding="utf-8")
        master = destination / "standalone-env"
        master.mkdir()
        (master / "Lib" / "site-packages").mkdir(parents=True)
        for name in ("python.exe", "uv.exe"):
            (master / name).write_bytes(b"test runtime")
        (destination / "manifest.json").write_text(
            json.dumps({"id": release.variant.value, "version": release.release_tag}),
            encoding="utf-8",
        )
        return destination

    def reject_venv(
        args: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Report the bounded uv failure before any real command is launched."""

        return subprocess.CompletedProcess(args, 1, "", "fixture failure")

    monkeypatch.setattr(StandaloneArtifactDownloader, "download", download)
    monkeypatch.setattr(StandaloneEnvironmentExtractor, "extract", extract)
    monkeypatch.setattr(subprocess, "run", reject_venv)


def test_refused_promotion_cannot_delete_existing_user_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected nonempty destination must survive the enclosing error handler."""

    _archive_boundaries(monkeypatch)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sentinel = workspace / "user-artwork.png"
    sentinel.write_bytes(b"keep exactly")

    with pytest.raises(StandaloneArtifactError, match="must be empty"):
        StandaloneEnvironmentProvisioner(catalog=_Catalog()).provision(
            workspace=workspace,
            variant=StandaloneVariantId.WINDOWS_CPU,
            cache_root=tmp_path / "cache",
        )

    assert sentinel.read_bytes() == b"keep exactly"


def test_failed_hydration_retains_verified_master_for_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed runtime creation must keep promoted assets and its pending phase."""

    _archive_boundaries(monkeypatch)
    workspace = tmp_path / "workspace"

    with pytest.raises(StandaloneArtifactError, match="fixture failure"):
        StandaloneEnvironmentProvisioner(catalog=_Catalog()).provision(
            workspace=workspace,
            variant=StandaloneVariantId.WINDOWS_CPU,
            cache_root=tmp_path / "cache",
        )

    assert (workspace / "main.py").is_file()
    assert (workspace / ".standalone-env" / "python.exe").is_file()
    assert StandaloneHydrationState(workspace).incomplete
