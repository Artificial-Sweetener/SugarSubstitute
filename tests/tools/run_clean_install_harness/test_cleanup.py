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

"""Tests for safe explicit clean-install harness targets."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.run_clean_install_harness import (
    CleanInstallHarnessError,
    _clean_install_root,
)


def test_clean_install_harness_refuses_non_default_target(tmp_path: Path) -> None:
    """Require the destructive-test opt-in for explicit cleanup targets."""

    target = tmp_path / "SugarSubstitute"
    target.mkdir()

    with pytest.raises(CleanInstallHarnessError, match="Refusing to clean"):
        _clean_install_root(target, log=lambda _message: None)


def test_clean_install_harness_cleans_named_opt_in_target(tmp_path: Path) -> None:
    """Clean explicitly opted-in disposable targets with the product name."""

    target = tmp_path / "SugarSubstitute"
    target.mkdir()
    (target / "fixture.txt").write_text("fixture", encoding="utf-8")

    _clean_install_root(
        target,
        allow_non_default_clean=True,
        log=lambda _message: None,
    )

    assert not target.exists()


def test_clean_install_harness_refuses_bad_opt_in_target_name(tmp_path: Path) -> None:
    """Retain the product-folder name guard for explicit cleanup overrides."""

    target = tmp_path / "not-the-product"
    target.mkdir()

    with pytest.raises(CleanInstallHarnessError, match="not named SugarSubstitute"):
        _clean_install_root(
            target,
            allow_non_default_clean=True,
            log=lambda _message: None,
        )
