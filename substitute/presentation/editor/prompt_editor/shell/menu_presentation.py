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

"""Own prompt-menu presentation and its non-modal measurement scope."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    MenuAnimationType,
    RoundMenu,
)

type _PromptMenuPresenter = Callable[
    [RoundMenu, object, bool, MenuAnimationType],
    object,
]


def _present_qfluent_menu(
    menu: RoundMenu,
    position: object,
    animated: bool,
    animation_type: MenuAnimationType,
) -> object:
    """Present one fully populated prompt menu through QFluentWidgets."""

    return RoundMenu.exec(menu, position, animated, animation_type)


def _suppress_prompt_menu(
    _menu: RoundMenu,
    _position: object,
    _animated: bool,
    _animation_type: MenuAnimationType,
) -> None:
    """Leave one fully built prompt menu unpresented."""


_PROMPT_MENU_PRESENTER: _PromptMenuPresenter = _present_qfluent_menu


def present_prompt_menu(
    menu: RoundMenu,
    position: object,
    animated: bool,
    animation_type: MenuAnimationType,
) -> object:
    """Present one populated menu through the active presentation policy."""

    return _PROMPT_MENU_PRESENTER(menu, position, animated, animation_type)


@contextmanager
def suppress_prompt_menu_presentation() -> Iterator[None]:
    """Build prompt menus without entering their modal presentation loop."""

    global _PROMPT_MENU_PRESENTER
    previous_presenter = _PROMPT_MENU_PRESENTER
    _PROMPT_MENU_PRESENTER = _suppress_prompt_menu
    try:
        yield
    finally:
        _PROMPT_MENU_PRESENTER = previous_presenter


__all__ = [
    "present_prompt_menu",
    "suppress_prompt_menu_presentation",
]
