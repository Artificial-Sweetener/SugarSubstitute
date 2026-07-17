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

"""Bridge installed legacy launchers into permanent self-update ownership."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from pathlib import Path
from typing import Any
import urllib.request
from urllib.parse import urlparse

from sugarsubstitute_shared.launcher_update.models import (
    LauncherInstallationRecord,
    LauncherRelease,
)
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update
from sugarsubstitute_shared.launcher_update.staging import LauncherBundleStager
from sugarsubstitute_shared.launcher_update.targets import (
    LauncherBundleTarget,
    detect_launcher_bundle_target,
)
from sugarsubstitute_shared.launcher_update.versions import compare_release_versions
from sugarsubstitute_shared.tls import SystemTrustTlsContext


_LOGGER = logging.getLogger(__name__)
_DEFAULT_MANIFEST_URL = (
    "https://github.com/Artificial-Sweetener/SugarSubstitute/"
    "releases/latest/download/manifest.json"
)
ManifestLoader = Callable[[str], object]
UpdateScheduler = Callable[..., int]


class LegacyLauncherUpdateBridge:
    """Update an installed pre-self-update launcher from the running app."""

    def __init__(
        self,
        *,
        target_detector: Callable[[], LauncherBundleTarget] = (
            detect_launcher_bundle_target
        ),
        manifest_loader: ManifestLoader | None = None,
        stager: LauncherBundleStager | None = None,
        scheduler: UpdateScheduler = schedule_launcher_update,
    ) -> None:
        """Store adapters while keeping update policy independently testable."""

        self._target_detector = target_detector
        self._manifest_loader = manifest_loader or _load_https_manifest
        self._stager = stager or LauncherBundleStager()
        self._scheduler = scheduler

    def run(self, *, install_root: Path) -> bool:
        """Stage a needed launcher update and return whether it was scheduled."""

        root = install_root.expanduser().resolve()
        config_path = root / "launcher" / "config.json"
        if not config_path.is_file():
            return False
        config = _load_config(config_path)
        if not _updates_enabled(config):
            return False
        target = self._target_detector()
        if not _is_installed_layout(root=root, target=target):
            return False
        manifest_url = _manifest_url(config)
        if manifest_url is None:
            return False
        release = LauncherRelease.from_manifest_json(
            self._manifest_loader(manifest_url),
            target_key=target.key,
        )
        if release.channel != _string(config, "channel", default="stable"):
            return False
        installation_path = root / "launcher" / "installation.json"
        installed = LauncherInstallationRecord.load(installation_path)
        if installed is not None:
            if installed.target_key != target.key:
                raise ValueError(
                    "Launcher installation target does not match this host."
                )
            if compare_release_versions(installed.version, release.version) >= 0:
                return False
        runtime_python = _owned_path(
            root=root,
            raw_value=_required_string(config, "runtime_python"),
        )
        if not runtime_python.is_file():
            _LOGGER.warning(
                "Skipping legacy launcher update because runtime Python is missing | "
                "runtime_python=%s",
                runtime_python,
            )
            return False
        request_path = self._stager.stage(
            install_root=root,
            version=release.version,
            target=target,
            asset=release.asset,
        )
        helper_pid = self._scheduler(
            request_path=request_path,
            runtime_python=runtime_python,
            app_dir=root / "app",
            relaunch=False,
            wait_pid=None,
        )
        _LOGGER.info(
            "Scheduled legacy launcher update | version=%s target=%s helper_pid=%d",
            release.version,
            target.key,
            helper_pid,
        )
        return True


def _load_https_manifest(url: str) -> object:
    """Fetch one production manifest with a bounded HTTPS request."""

    if urlparse(url).scheme != "https":
        raise ValueError("Launcher manifest URLs must use HTTPS.")
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(
        request,
        timeout=30.0,
        context=SystemTrustTlsContext.create(),
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_config(path: Path) -> dict[str, Any]:
    """Load the small launcher-owned config needed by the migration bridge."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported launcher config schema.")
    return payload


def _updates_enabled(config: dict[str, Any]) -> bool:
    """Respect the user's persisted automatic update preference."""

    update_check = config.get("update_check")
    return (
        not isinstance(update_check, dict) or update_check.get("enabled") is not False
    )


def _manifest_url(config: dict[str, Any]) -> str | None:
    """Return the configured release manifest URL."""

    if "release_source" not in config:
        return _DEFAULT_MANIFEST_URL
    release_source = config.get("release_source")
    if release_source is None:
        return None
    if not isinstance(release_source, dict):
        raise ValueError("Installed launcher has no release source.")
    if release_source.get("kind") != "github_release_manifest":
        raise ValueError("Installed launcher release source is unsupported.")
    return _required_string(release_source, "manifest_url")


def _is_installed_layout(*, root: Path, target: LauncherBundleTarget) -> bool:
    """Exclude development checkouts and incomplete installs from the bridge."""

    return (
        (root / "app" / "main.py").is_file()
        and (root / target.executable_relative_path).is_file()
        and (root / target.support_relative_path).is_dir()
    )


def _owned_path(*, root: Path, raw_value: str) -> Path:
    """Resolve a configured path and require it to remain in the install root."""

    path = Path(raw_value).expanduser().resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Launcher config path escapes the install root: {path}")
    return path


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read one required nonempty string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Required launcher config field is missing: {key}")
    return value


def _string(payload: dict[str, Any], key: str, *, default: str) -> str:
    """Read one optional nonempty string."""

    value = payload.get(key)
    return value if isinstance(value, str) and value else default


__all__ = ["LegacyLauncherUpdateBridge"]
