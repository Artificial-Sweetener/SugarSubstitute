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

"""Verify launcher command-line parsing at the application entry boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.cli import parse_launcher_args


def test_launcher_args_parse_internal_flags(tmp_path: Path) -> None:
    """Accept setup, repair, update, and install-root flags."""

    install_root = tmp_path / "SugarSubstitute"
    args = parse_launcher_args(
        [
            "--continue-install",
            "--repair",
            "--no-update-check",
            "--install-root",
            str(install_root),
            "--handoff-geometry",
            "10,20,1260,800",
            "--locale",
            "ja-JP",
        ]
    )

    assert args.continue_install is True
    assert args.repair is True
    assert args.no_update_check is True
    assert args.handoff_geometry == "10,20,1260,800"
    assert args.install_root == install_root
    assert args.headless_install is False
    assert args.verify_release_connectivity is False
    assert args.manifest_url is None
    assert args.locale_override == "ja"


def test_launcher_args_parse_headless_release_probe_flags(tmp_path: Path) -> None:
    """Accept an explicit release source for packaged Linux validation modes."""

    install_root = tmp_path / "SugarSubstitute"
    manifest_url = "https://github.com/acme/releases/download/test/manifest.json"

    install_args = parse_launcher_args(
        [
            "--headless-install",
            "--install-root",
            str(install_root),
            "--manifest-url",
            manifest_url,
        ]
    )
    connectivity_args = parse_launcher_args(
        ["--verify-release-connectivity", "--manifest-url", manifest_url]
    )

    assert install_args.headless_install is True
    assert install_args.install_root == install_root
    assert install_args.manifest_url == manifest_url
    assert connectivity_args.verify_release_connectivity is True
    assert connectivity_args.manifest_url == manifest_url
    assert install_args.locale_override is None
    assert connectivity_args.locale_override is None


def test_launcher_args_reject_unsupported_locale_override() -> None:
    """Reject unshipped and automatic locale values at the launcher boundary."""

    with pytest.raises(SystemExit):
        parse_launcher_args(["--locale", "zh-TW"])


def test_headless_install_requires_explicit_install_root() -> None:
    """Prevent headless installation from inferring a mutable target path."""

    with pytest.raises(SystemExit):
        parse_launcher_args(["--headless-install"])
