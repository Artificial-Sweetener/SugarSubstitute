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

"""Tests for suppressing the QFluentWidgets Pro import banner."""

import builtins
from typing import TYPE_CHECKING

from substitute.shared.qfluentwidgets_banner import (
    QFLUENTWIDGETS_PRO_BANNER_TEXT,
    install_qfluentwidgets_banner_filter,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_qfluentwidgets_pro_banner_filter_suppresses_only_banner(
    monkeypatch: "MonkeyPatch",
) -> None:
    """The global print filter should drop only the QFluentWidgets Pro banner."""

    printed: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_print(*args: object, **kwargs: object) -> None:
        """Capture non-filtered print calls."""

        printed.append((args, kwargs))

    monkeypatch.setattr(builtins, "print", fake_print)

    install_qfluentwidgets_banner_filter()
    builtins.print(f"Tips: {QFLUENTWIDGETS_PRO_BANNER_TEXT}")
    builtins.print("ordinary console output", end="\n")

    assert printed == [(("ordinary console output",), {"end": "\n"})]
