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

"""Build shared CivitAI page actions for model metadata UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from qfluentwidgets.components.widgets.menu import Action  # type: ignore[import-untyped]

CIVITAI_PAGE_ACTION_TEXT = "Go to CivitAI page"
UrlOpener = Callable[[str], bool]


def open_external_url(url: str) -> bool:
    """Open one external URL through the desktop shell."""

    return QDesktopServices.openUrl(QUrl(url))


def civitai_page_action(
    model_page_url: str | None,
    open_url: UrlOpener,
) -> Action | None:
    """Return a CivitAI page action when a non-blank page URL is available."""

    normalized_model_page_url = model_page_url.strip() if model_page_url else ""
    if not normalized_model_page_url:
        return None
    action = Action(CIVITAI_PAGE_ACTION_TEXT)
    action.triggered.connect(
        lambda _checked=False, url=normalized_model_page_url: open_url(url)
    )
    return action


__all__ = [
    "CIVITAI_PAGE_ACTION_TEXT",
    "UrlOpener",
    "civitai_page_action",
    "open_external_url",
]
