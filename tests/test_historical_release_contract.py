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

"""Verify immutable resolver contracts for historical installer qualification."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.ci.historical_release_contract import (
    HistoricalReleaseContractError,
    historical_install_environment,
)


def test_historical_install_environment_limits_only_the_historical_resolver() -> None:
    """A released install should resolve against its publication-time index view."""

    source = {
        "QUALIFICATION": "1",
        "UV_EXCLUDE_NEWER": "false",
    }

    environment = historical_install_environment(
        source,
        published_at="2026-08-12T00:27:36Z",
        install_root=Path("historical-install"),
    )

    assert environment == {
        "QUALIFICATION": "1",
        "SUGAR_SUBSTITUTE_STARTUP_HARNESS_COMFY_OUTPUT_LOG": str(
            (
                Path("historical-install") / "historical-managed-comfy-startup.log"
            ).resolve()
        ),
        "UV_EXCLUDE_NEWER": "2026-08-12T00:27:36Z",
    }
    assert source["UV_EXCLUDE_NEWER"] == "false"


@pytest.mark.parametrize(
    "published_at",
    ["", "not-a-timestamp", "2026-08-12T00:27:36"],
)
def test_historical_install_environment_rejects_unsafe_cutoffs(
    published_at: str,
) -> None:
    """Qualification must not accept a missing, malformed, or timezone-free cutoff."""

    with pytest.raises(HistoricalReleaseContractError):
        historical_install_environment(
            {},
            published_at=published_at,
            install_root=Path("historical-install"),
        )
