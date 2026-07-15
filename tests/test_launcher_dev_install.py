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

"""Tests for the clean local developer install proof harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.dev_install import (
    DEFAULT_INSTALL_ROOT,
    DevInstallError,
    _parse_args,
    clean_install_root,
    onboarding_probe_environment,
)
from launcher.sugarsubstitute_launcher.platforms import (
    LINUX_X64,
    MACOS_ARM64,
    WINDOWS_X64,
    LauncherTarget,
)


def test_default_dev_install_root_stays_inside_repo_tmp() -> None:
    """The developer proof must not use a maintainer's manual install target."""

    assert DEFAULT_INSTALL_ROOT.name == "SugarSubstitute"
    assert ".pytest-tmp" in DEFAULT_INSTALL_ROOT.parts


def test_clean_install_root_refuses_non_default_without_override(
    tmp_path: Path,
) -> None:
    """Cleaning is pinned to the disposable target unless tests override it."""

    target = tmp_path / "SugarSubstitute"
    target.mkdir()

    with pytest.raises(DevInstallError, match="non-default install root"):
        clean_install_root(target)

    assert target.is_dir()


def test_clean_install_root_deletes_named_override_target(tmp_path: Path) -> None:
    """The test override still requires a path named SugarSubstitute."""

    target = tmp_path / "SugarSubstitute"
    (target / "old.txt").parent.mkdir(parents=True)
    (target / "old.txt").write_text("old", encoding="utf-8")

    clean_install_root(target, allow_non_default_clean=True, log=lambda _line: None)

    assert not target.exists()


def test_clean_install_root_refuses_bad_override_name(tmp_path: Path) -> None:
    """The cleaner refuses broad or ambiguous path names even with override."""

    target = tmp_path / "NotSugarSubstitute"
    target.mkdir()

    with pytest.raises(DevInstallError, match="not named SugarSubstitute"):
        clean_install_root(target, allow_non_default_clean=True)

    assert target.is_dir()


def test_dev_install_cli_requires_explicit_non_default_clean_override() -> None:
    """The CI clean override is opt-in and independently parsed."""

    default_args = _parse_args([])
    override_args = _parse_args(["--allow-non-default-clean"])

    assert default_args.allow_non_default_clean is False
    assert override_args.allow_non_default_clean is True


@pytest.mark.parametrize("target", [WINDOWS_X64, LINUX_X64])
def test_onboarding_probe_uses_offscreen_qt_on_headless_targets(
    target: LauncherTarget,
) -> None:
    """Windows and Linux probes can construct the onboarding window headlessly."""

    environment = onboarding_probe_environment(target)

    assert environment["QT_QPA_PLATFORM"] == "offscreen"


def test_onboarding_probe_uses_native_cocoa_on_macos() -> None:
    """macOS avoids Qt's offscreen backend because frameless windows require Cocoa."""

    environment = onboarding_probe_environment(MACOS_ARM64)

    assert "QT_QPA_PLATFORM" not in environment
    assert environment["SUBSTITUTE_DISABLE_APP_USER_MODEL_ID"] == "1"
