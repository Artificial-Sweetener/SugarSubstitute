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

"""Verify Output canvas floating chrome stylesheet application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from substitute.presentation.canvas.output.output_canvas_chrome_controller import (
    OutputCanvasChromeController,
)
from substitute.presentation.canvas.output.output_canvas_chrome import (
    install_output_navigation_chrome_theme_refresh,
)


def test_navigation_background_stylesheet_uses_current_theme_colors() -> None:
    """Navigation background stylesheet should use injected theme color providers."""

    controller = _controller(surface="rgba(1, 2, 3, 0.5)", border="rgba(4, 5, 6, 1)")

    stylesheet = controller.navigation_background_stylesheet()

    assert "background-color: rgba(1, 2, 3, 0.5);" in stylesheet
    assert "border: 1px solid rgba(4, 5, 6, 1);" in stylesheet
    assert "border-radius: 8px;" in stylesheet
    assert "padding: 0px;" in stylesheet


def test_apply_navigation_background_styles_updates_both_surfaces() -> None:
    """Chrome controller should style base and comparison backgrounds together."""

    base = _StyledWidget()
    comparison = _StyledWidget()

    _controller().apply_navigation_background_styles(
        base_background=base,
        comparison_background=comparison,
    )

    assert len(base.stylesheets) == 1
    assert comparison.stylesheets == base.stylesheets


def test_apply_navigation_background_styles_allows_missing_comparison() -> None:
    """Missing comparison background should not block base background styling."""

    base = _StyledWidget()

    _controller().apply_navigation_background_styles(
        base_background=base,
        comparison_background=None,
    )

    assert len(base.stylesheets) == 1


def test_install_output_navigation_chrome_theme_refresh_applies_and_registers() -> None:
    """Chrome theme installation should apply immediately and subscribe to refresh."""

    host = object()
    base = _StyledWidget()
    comparison = _StyledWidget()
    connected: list[tuple[object, Callable[[], None]]] = []

    install_output_navigation_chrome_theme_refresh(
        host=host,
        base_background=base,
        comparison_background=comparison,
        connect_refresh=lambda widget, refresh: connected.append((widget, refresh)),
        surface_rgba=lambda: "rgba(1, 2, 3, 4)",
        border_rgba=lambda: "rgba(5, 6, 7, 8)",
    )

    assert len(connected) == 1
    assert connected[0][0] is host
    assert callable(connected[0][1])
    assert "rgba(1, 2, 3, 4)" in base.stylesheets[0]
    assert comparison.stylesheets == base.stylesheets


def test_output_navigation_chrome_theme_refresh_uses_latest_colors() -> None:
    """Registered chrome refresh callback should rebuild styles with current colors."""

    base = _StyledWidget()
    colors = {
        "surface": "rgba(1, 1, 1, 1)",
        "border": "rgba(2, 2, 2, 2)",
    }
    refreshes: list[Callable[[], None]] = []

    install_output_navigation_chrome_theme_refresh(
        host=object(),
        base_background=base,
        comparison_background=None,
        connect_refresh=lambda _widget, refresh: refreshes.append(refresh),
        surface_rgba=lambda: colors["surface"],
        border_rgba=lambda: colors["border"],
    )

    colors["surface"] = "rgba(3, 3, 3, 3)"
    colors["border"] = "rgba(4, 4, 4, 4)"
    refreshes[0]()

    assert "rgba(1, 1, 1, 1)" in base.stylesheets[0]
    assert "rgba(3, 3, 3, 3)" in base.stylesheets[1]
    assert "rgba(4, 4, 4, 4)" in base.stylesheets[1]


@dataclass(slots=True)
class _StyledWidget:
    """Small widget double that records assigned stylesheets."""

    stylesheets: list[str] = field(default_factory=list)

    def setStyleSheet(self, stylesheet: str) -> None:  # noqa: N802
        """Record one stylesheet assignment."""

        self.stylesheets.append(stylesheet)


def _controller(
    *,
    surface: str = "rgba(10, 20, 30, 0.75)",
    border: str = "rgba(1, 1, 1, 0.4)",
) -> OutputCanvasChromeController:
    """Return a chrome controller with deterministic color providers."""

    return OutputCanvasChromeController(
        surface_rgba=lambda: surface,
        border_rgba=lambda: border,
    )
