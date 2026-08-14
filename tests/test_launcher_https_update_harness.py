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

"""Tests for the private HTTPS launcher update harness."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import (
    RELEASE_SOURCE_KIND_GITHUB,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError
from tools.ci.installer_ui_qualification import assert_startup_trace_sequence
from tools.ci.verify_installer_lifecycle import set_update_manifest
from tools.run_https_update_harness import (
    DEFAULT_HARNESS_ROOT,
    NEW_VERSION,
    run_https_update_harness,
)


def test_https_update_harness_installs_remote_payload() -> None:
    """The headless harness should prove HTTPS manifest and payload updates."""

    if shutil.which("openssl") is None:
        pytest.skip("OpenSSL is required to generate the local HTTPS test cert.")

    result = run_https_update_harness(keep_artifacts=False)

    assert result.installed_version == NEW_VERSION
    assert result.manifest_url.startswith("https://localhost:")
    assert result.asset_url.startswith("https://localhost:")
    assert result.request_paths == (
        "/manifest.json",
        f"/SugarSubstitute-app-v{NEW_VERSION}.zip",
    )
    assert not DEFAULT_HARNESS_ROOT.exists()


def test_lifecycle_candidate_manifest_preserves_release_source_contract(
    tmp_path: Path,
) -> None:
    """The upgrade verifier should write config loadable by historical launchers."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    candidate_manifest_url = "https://localhost:44443/manifest.json"

    set_update_manifest(layout.root, candidate_manifest_url)

    updated_config = LauncherConfig.load(layout.config_path)
    assert updated_config.release_source is not None
    assert updated_config.release_source.kind == RELEASE_SOURCE_KIND_GITHUB
    assert updated_config.release_source.manifest_url == candidate_manifest_url


def test_lifecycle_requires_ordered_splash_to_main_shell_trace(tmp_path: Path) -> None:
    """The install proof should accept only the production reveal sequence."""

    trace_path = tmp_path / "startup-trace.jsonl"
    trace_path.write_text(
        "\n".join(
            json.dumps({"event": event})
            for event in (
                "launch_splash.started",
                "launch_splash.closed",
                "main_shell.shown",
            )
        ),
        encoding="utf-8",
    )

    assert_startup_trace_sequence(trace_path)


def test_lifecycle_rejects_main_shell_without_completed_splash(tmp_path: Path) -> None:
    """A main-window event alone must not count as button-launch proof."""

    trace_path = tmp_path / "startup-trace.jsonl"
    trace_path.write_text(
        json.dumps({"event": "main_shell.shown"}),
        encoding="utf-8",
    )

    with pytest.raises(InstallerLifecycleError, match="splash-to-shell sequence"):
        assert_startup_trace_sequence(trace_path)
