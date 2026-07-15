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

"""Suppress the QFluentWidgets Pro import banner emitted at module import time."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable, Final, cast

QFLUENTWIDGETS_PRO_BANNER_TEXT: Final = "QFluentWidgets Pro is now released."
_FILTER_MARKER = "_sugarsubstitute_qfluentwidgets_banner_filter"
_ORIGINAL_PRINT = "_sugarsubstitute_original_print"
_PrintFunc = Callable[..., None]


def is_qfluentwidgets_import_banner(args: tuple[object, ...]) -> bool:
    """Return whether print arguments match the known QFluentWidgets banner."""

    rendered = " ".join(str(arg) for arg in args)
    return QFLUENTWIDGETS_PRO_BANNER_TEXT in rendered


def install_qfluentwidgets_banner_filter() -> None:
    """Install a process-wide print filter for the known QFluentWidgets banner."""

    current_print = cast(_PrintFunc, builtins.print)
    if getattr(current_print, _FILTER_MARKER, False):
        return

    original_print = current_print

    def filtered_print(*args: object, **kwargs: Any) -> None:
        """Drop only the known import banner while preserving all other prints."""

        if is_qfluentwidgets_import_banner(args):
            return
        original_print(*args, **kwargs)

    setattr(filtered_print, _FILTER_MARKER, True)
    setattr(filtered_print, _ORIGINAL_PRINT, original_print)
    builtins.print = filtered_print


@contextmanager
def suppress_qfluentwidgets_import_banner() -> Iterator[None]:
    """Temporarily suppress the QFluentWidgets banner for scoped imports."""

    original_print = cast(_PrintFunc, builtins.print)

    def filtered_print(*args: object, **kwargs: Any) -> None:
        """Drop only the known import banner while preserving all other prints."""

        if is_qfluentwidgets_import_banner(args):
            return
        original_print(*args, **kwargs)

    builtins.print = filtered_print
    try:
        yield
    finally:
        builtins.print = original_print


__all__ = [
    "QFLUENTWIDGETS_PRO_BANNER_TEXT",
    "install_qfluentwidgets_banner_filter",
    "is_qfluentwidgets_import_banner",
    "suppress_qfluentwidgets_import_banner",
]
