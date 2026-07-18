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

"""Download, verify, and stage immutable launcher update bundles."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from sugarsubstitute_shared.launcher_version import safe_launcher_version
from sugarsubstitute_shared.launcher_update.archive import safe_extract_zip
from sugarsubstitute_shared.launcher_update.downloader import (
    LauncherBundleDownloader,
)
from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
    LauncherUpdateRequest,
)
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


class LauncherBundleValidationError(RuntimeError):
    """Report a launcher bundle that does not match its target contract."""


class LauncherBundleStager:
    """Own verified bundle staging without touching the running launcher."""

    def __init__(
        self,
        *,
        downloader: LauncherBundleDownloader | None = None,
    ) -> None:
        """Store the asset downloader used by this stager."""

        self._downloader = downloader or LauncherBundleDownloader()

    def stage(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
    ) -> Path:
        """Stage one validated update and return its persisted request path."""

        resolved_root = install_root.expanduser().resolve()
        update_root = resolved_root / "launcher" / "updates"
        version_root = update_root / "staging" / safe_launcher_version(version)
        archive_path = update_root / "downloads" / asset.filename
        self._downloader.download(asset=asset, destination=archive_path)
        _verify_sha256(archive_path, expected=asset.sha256)
        if version_root.exists():
            shutil.rmtree(version_root)
        safe_extract_zip(zip_path=archive_path, destination_dir=version_root)
        normalize_staged_bundle_permissions(bundle_dir=version_root, target=target)
        validate_staged_bundle(bundle_dir=version_root, target=target)
        request_path = update_root / "pending.json"
        LauncherUpdateRequest(
            install_root=resolved_root,
            version=version,
            target_key=target.key,
            staged_bundle_dir=version_root,
            relaunch=False,
        ).save(request_path)
        return request_path


def validate_staged_bundle(
    *,
    bundle_dir: Path,
    target: LauncherBundleTarget,
) -> None:
    """Validate required paths and reject unexpected top-level content."""

    if not (bundle_dir / target.executable_relative_path).is_file():
        raise LauncherBundleValidationError(
            "Launcher bundle is missing its target executable."
        )
    if not (bundle_dir / target.support_relative_path).is_dir():
        raise LauncherBundleValidationError(
            "Launcher bundle is missing its runtime support directory."
        )
    allowed_roots = {path.parts[0] for path in target.replacement_roots}
    unexpected = sorted(
        child.name for child in bundle_dir.iterdir() if child.name not in allowed_roots
    )
    if unexpected:
        raise LauncherBundleValidationError(
            f"Launcher bundle contains unexpected roots: {', '.join(unexpected)}"
        )


def normalize_staged_bundle_permissions(
    *,
    bundle_dir: Path,
    target: LauncherBundleTarget,
) -> None:
    """Restore target-required execute permissions after portable extraction."""

    if target.executable_mode is None:
        return
    executable_path = bundle_dir / target.executable_relative_path
    if executable_path.is_file():
        executable_path.chmod(executable_path.stat().st_mode | target.executable_mode)


def _verify_sha256(path: Path, *, expected: str) -> None:
    """Reject an asset whose bytes differ from the release manifest."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected.lower():
        raise LauncherBundleValidationError(
            f"Launcher bundle SHA256 mismatch: {path.name}"
        )


__all__ = [
    "LauncherBundleStager",
    "LauncherBundleValidationError",
    "normalize_staged_bundle_permissions",
    "validate_staged_bundle",
]
