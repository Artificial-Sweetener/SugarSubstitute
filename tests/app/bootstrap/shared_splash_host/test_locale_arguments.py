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

"""Test shared splash-host locale argument normalization."""

from __future__ import annotations

from substitute.app.bootstrap.shared_splash_host import _parse_args


def test_splash_host_locale_argument_uses_shared_validation() -> None:
    """Normalize the launcher or direct-app handoff before creating widgets."""

    assert _parse_args(["--locale=zh_CN"]).locale == "zh-Hans"
    assert _parse_args(["--locale=ja-JP"]).locale == "ja"


def test_splash_host_has_no_slow_operation_lifetime_timeout_by_default() -> None:
    """Production splash ownership should continue until completion or failure."""

    assert _parse_args([]).maximum_lifetime_seconds == 0.0
