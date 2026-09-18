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

"""Verify pending launcher preparations retain independent request and payload inputs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import zipfile

import pytest

from sugarsubstitute_shared.launcher_update.archive import SecureArchiveError
from sugarsubstitute_shared.launcher_update.downloader import LauncherBundleDownloader
from sugarsubstitute_shared.launcher_update.models import LauncherBundleAsset
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE

from .support import _asset, _write_bundle


@pytest.mark.parametrize("replacement", ["valid", "invalid"])
def test_preparing_same_version_preserves_pending_request_and_payload(
    tmp_path: Path, replacement: str
) -> None:
    """Keep the first pending input intact even if another preparation fails."""
    first_archive = _write_bundle(tmp_path / "first.zip", marker="first")
    second_archive = tmp_path / "second.zip"
    if replacement == "valid":
        _write_bundle(second_archive, marker="second")
    else:
        with zipfile.ZipFile(second_archive, "w") as archive:
            archive.writestr("../escape.txt", "invalid")
    stager = LauncherBundleStager()
    root = tmp_path / "installation"
    first_path = stager.stage(
        install_root=root,
        version="1.2.3",
        target=WINDOWS_X64_BUNDLE,
        asset=_asset(first_archive),
    )
    first = LauncherUpdateRequest.load(first_path)
    first_request_bytes = first_path.read_bytes()
    if replacement == "invalid":
        with pytest.raises(SecureArchiveError):
            stager.stage(
                install_root=root,
                version="1.2.3",
                target=WINDOWS_X64_BUNDLE,
                asset=_asset(second_archive),
            )
    else:
        second_path = stager.stage(
            install_root=root,
            version="1.2.3",
            target=WINDOWS_X64_BUNDLE,
            asset=_asset(second_archive),
        )
        second = LauncherUpdateRequest.load(second_path)
        assert second_path != first_path
        assert second.staged_bundle_dir != first.staged_bundle_dir
        assert (second.staged_bundle_dir / "SugarSubstitute.exe").read_text(
            encoding="utf-8"
        ) == "second"
    assert first_path.read_bytes() == first_request_bytes
    assert (first.staged_bundle_dir / "SugarSubstitute.exe").read_text(
        encoding="utf-8"
    ) == "first"


def test_overlapping_preparations_keep_same_named_archives_separate(
    tmp_path: Path,
) -> None:
    """Force both downloads to finish before verification without sharing bytes."""
    downloaded = Barrier(2)

    class Downloader(LauncherBundleDownloader):
        """Coordinate real local downloads at their verification boundary."""

        def download(self, *, asset: LauncherBundleAsset, destination: Path) -> Path:
            """Expose overlapping completed downloads without timing assumptions."""
            result = super().download(asset=asset, destination=destination)
            downloaded.wait(timeout=5)
            return result

    assets: list[LauncherBundleAsset] = []
    for marker in ("first", "second"):
        directory = tmp_path / marker
        directory.mkdir()
        assets.append(_asset(_write_bundle(directory / "same-name.zip", marker=marker)))
    stager = LauncherBundleStager(downloader=Downloader())
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(
                stager.stage,
                install_root=tmp_path / "installation",
                version="1.2.3",
                target=WINDOWS_X64_BUNDLE,
                asset=asset,
            )
            for asset in assets
        ]
        paths = [future.result(timeout=10) for future in pending]
    assert len(set(paths)) == 2
    payloads = [LauncherUpdateRequest.load(path).staged_bundle_dir for path in paths]
    assert [
        (root / "SugarSubstitute.exe").read_text(encoding="utf-8") for root in payloads
    ] == ["first", "second"]
