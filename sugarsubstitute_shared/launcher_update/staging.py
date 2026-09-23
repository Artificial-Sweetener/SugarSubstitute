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
from collections.abc import Callable
import logging
import shutil
from pathlib import Path
from uuid import uuid4
from tempfile import TemporaryDirectory

from sugarsubstitute_shared.launcher_version import safe_launcher_version
from sugarsubstitute_shared.launcher_update.archive import safe_extract_zip
from sugarsubstitute_shared.launcher_update.downloader import (
    LauncherBundleDownloader,
)
from sugarsubstitute_shared.launcher_update.models import (
    LauncherBundleAsset,
)
from sugarsubstitute_shared.launcher_update.request import LauncherUpdateRequest
from sugarsubstitute_shared.launcher_update.bundle_validation import (
    LauncherBundleValidationError,
    validate_launcher_bundle,
)
from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget
from sugarsubstitute_shared.launcher_update.delegation_contract import (
    validate_launcher_successor,
)
from sugarsubstitute_shared.windows_long_paths import operational_path
from sugarsubstitute_shared.asset_transfer import ObservedActivity


class LauncherBundleStager:
    """Own verified bundle staging without touching the running launcher."""

    def __init__(
        self,
        *,
        downloader: LauncherBundleDownloader | None = None,
        activity_observer: Callable[[], None] | None = None,
    ) -> None:
        """Store the asset downloader used by this stager."""

        self._downloader = downloader or LauncherBundleDownloader()
        self._activity_observer = activity_observer

    def stage(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
    ) -> Path:
        """Stage one validated update and return its persisted request path."""

        resolved_root = operational_path(install_root).resolve()
        update_root = resolved_root / "launcher" / "updates"
        attempt_root = (
            update_root / "staging" / safe_launcher_version(version) / uuid4().hex
        )
        attempt_root.mkdir(parents=True)
        try:
            version_root = self.stage_bundle(
                install_root=resolved_root,
                version=version,
                target=target,
                asset=asset,
                destination_dir=attempt_root / "payload",
            )
            validate_launcher_successor(
                baseline=resolved_root, candidate=version_root, target=target
            )
            request_path = attempt_root / "request.json"
            LauncherUpdateRequest(
                install_root=resolved_root,
                version=version,
                target_key=target.key,
                staged_bundle_dir=version_root,
                relaunch=False,
            ).save(request_path)
            return request_path
        except BaseException:
            try:
                shutil.rmtree(attempt_root)
            except OSError:
                logging.getLogger(__name__).exception(
                    "Failed launcher staging could not be removed | attempt=%s",
                    attempt_root,
                )
            raise

    def stage_bundle(
        self,
        *,
        install_root: Path,
        version: str,
        target: LauncherBundleTarget,
        asset: LauncherBundleAsset,
        destination_dir: Path,
    ) -> Path:
        """Download and validate a bundle without creating a promotion request."""

        resolved_root = operational_path(install_root).resolve()
        destination = operational_path(destination_dir).resolve()
        if destination == resolved_root or not destination.is_relative_to(
            resolved_root
        ):
            raise LauncherBundleValidationError(
                f"Launcher staging path escapes its installation: {destination}"
            )
        update_root = resolved_root / "launcher" / "updates"
        download_root = update_root / "downloads"
        download_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="bundle-", dir=download_root) as temporary:
            archive_path = Path(temporary) / "bundle.zip"
            self._downloader.download(asset=asset, destination=archive_path)
            _verify_sha256(
                archive_path,
                expected=asset.sha256,
                activity_observer=self._activity_observer,
            )
            if destination.exists():
                shutil.rmtree(destination)
            safe_extract_zip(
                zip_path=archive_path,
                destination_dir=destination,
                activity_observer=self._activity_observer,
            )
            normalize_staged_bundle_permissions(bundle_dir=destination, target=target)
            validate_launcher_bundle(bundle_dir=destination, target=target)
        return destination


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


def _verify_sha256(
    path: Path,
    *,
    expected: str,
    activity_observer: Callable[[], None] | None = None,
) -> None:
    """Reject an asset whose bytes differ from the release manifest."""

    digest = hashlib.sha256()
    activity = ObservedActivity(activity_observer)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            activity.record()
    if digest.hexdigest().lower() != expected.lower():
        raise LauncherBundleValidationError(
            f"Launcher bundle SHA256 mismatch: {path.name}"
        )


__all__ = [
    "LauncherBundleStager",
    "normalize_staged_bundle_permissions",
]
