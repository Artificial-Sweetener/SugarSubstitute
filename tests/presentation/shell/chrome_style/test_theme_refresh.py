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

"""Verify global theme callback lifecycle ownership."""

from __future__ import annotations

import pytest

from substitute.presentation.shell import chrome_style
from tests.presentation.shell.chrome_style.support import ThemeConfig, ThemeWidget


def _install_theme_doubles(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ThemeConfig, ThemeWidget]:
    """Install an isolated theme configuration and live widget."""
    config = ThemeConfig()
    widget = ThemeWidget()
    monkeypatch.setattr(chrome_style, "qconfig", config)
    monkeypatch.setattr(chrome_style, "_shiboken_is_valid", lambda _obj: True)
    return config, widget


def test_theme_refresh_disconnects_when_widget_is_destroyed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release global QFluent callbacks with their owning widget."""
    config, widget = _install_theme_doubles(monkeypatch)
    calls: list[str] = []

    chrome_style.connect_theme_refresh(widget, lambda: calls.append("refresh"))
    config.themeChangedFinished.emit()
    widget.destroyed.emit()
    config.themeColorChanged.emit()

    assert calls == ["refresh"]
    assert config.themeChangedFinished.callbacks == []
    assert config.themeColorChanged.callbacks == []


def test_theme_refresh_detaches_deleted_qt_wrappers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detach a deleted Qt wrapper after its first failed refresh."""
    config, widget = _install_theme_doubles(monkeypatch)

    def raise_deleted() -> None:
        """Mimic PySide's deleted C++ object error."""
        raise RuntimeError("Internal C++ object (PromptEditor) already deleted.")

    chrome_style.connect_theme_refresh(widget, raise_deleted)
    config.themeChangedFinished.emit()
    config.themeChangedFinished.emit()

    assert config.themeChangedFinished.callbacks == []
    assert config.themeColorChanged.callbacks == []


def test_theme_refresh_reraises_unexpected_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep non-lifecycle failures visible to callers."""
    config, widget = _install_theme_doubles(monkeypatch)

    def raise_unexpected() -> None:
        """Raise an error unrelated to Qt destruction."""
        raise RuntimeError("boom")

    chrome_style.connect_theme_refresh(widget, raise_unexpected)

    with pytest.raises(RuntimeError, match="boom"):
        config.themeChangedFinished.emit()

    assert len(config.themeChangedFinished.callbacks) == 1
    assert len(config.themeColorChanged.callbacks) == 1
