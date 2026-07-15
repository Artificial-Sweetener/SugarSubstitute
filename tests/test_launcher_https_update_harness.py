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

import shutil

import pytest

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
