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

"""Verify Output navigation selector text, elision, and width metrics."""

from __future__ import annotations


from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    scene_selector_current_width,
    selector_display_text,
    selector_display_text_for_metrics,
    selector_font_metrics_for_widget,
    selector_current_width,
    selector_text_width,
    selector_width_for_text,
    selector_width_for_metrics_text,
    selector_width_for_widget_text,
    source_selector_current_width,
    source_selector_full_text,
)


def test_source_selector_full_text_prefers_active_source_label() -> None:
    """Collapsed source selector labels should prefer the active source."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert (
        source_selector_full_text(sources, active_source_key="wf:upscale") == "Upscale"
    )


def test_source_selector_full_text_falls_back_to_first_source() -> None:
    """Collapsed source selector labels should fall back to visible source order."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert source_selector_full_text(sources, active_source_key="missing") == "Text"


def test_source_selector_full_text_uses_output_without_sources() -> None:
    """Collapsed source selector labels should have a stable empty-state label."""

    assert source_selector_full_text((), active_source_key=None) == "Output"


def test_selector_display_text_keeps_fitting_text() -> None:
    """Selector display text should preserve labels within available width."""

    assert (
        selector_display_text(
            "Portrait",
            text_width=64,
            max_width=120,
            horizontal_padding=24,
        )
        == "Portrait"
    )


def test_selector_display_text_uses_elide_adapter_for_overflow() -> None:
    """Selector display text should delegate host-specific elision when available."""

    calls: list[tuple[str, int]] = []

    def _elide(text: str, width: int) -> str:
        calls.append((text, width))
        return "Long..."

    assert (
        selector_display_text(
            "Long Authored Scene Name",
            text_width=220,
            max_width=120,
            horizontal_padding=24,
            elide_text=_elide,
        )
        == "Long..."
    )
    assert calls == [("Long Authored Scene Name", 96)]


def test_selector_display_text_uses_deterministic_fallback() -> None:
    """Selector display text should stay bounded without host elision support."""

    assert (
        selector_display_text(
            "Long Authored Scene Name",
            text_width=220,
            max_width=64,
            horizontal_padding=16,
            fallback_chrome_width=36,
        )
        == "Lon..."
    )


def test_selector_width_for_text_respects_bounds_and_padding() -> None:
    """Selector width should add chrome padding and clamp to design bounds."""

    assert (
        selector_width_for_text(
            20,
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 58
    )
    assert (
        selector_width_for_text(
            96,
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 124
    )
    assert (
        selector_width_for_text(
            400,
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 260
    )


def test_selector_font_metrics_for_widget_uses_host_widget_metrics() -> None:
    """Selector metric adapters should read opaque host widget metrics."""

    metrics = object()

    class _Widget:
        """Provide host-like font metrics."""

        def fontMetrics(self) -> object:
            """Return the configured metrics object."""

            return metrics

    assert selector_font_metrics_for_widget(_Widget()) is metrics
    assert selector_font_metrics_for_widget(None) is not metrics


def test_selector_text_width_uses_host_metrics_or_fallback() -> None:
    """Selector text width should prefer host metrics and keep a stable fallback."""

    class _Metrics:
        """Provide host-like text width measurement."""

        def horizontalAdvance(self, text: str) -> int:
            """Return deterministic text width."""

            return len(text) * 11

    assert selector_text_width("Scene", _Metrics()) == 55
    assert selector_text_width("Scene", object()) == 35


def test_selector_display_text_for_metrics_uses_host_elision() -> None:
    """Selector display text should keep toolkit-specific elision behind a port."""

    calls: list[tuple[str, object, int]] = []

    class _Metrics:
        """Capture host elision calls."""

        def horizontalAdvance(self, text: str) -> int:
            """Return an overflowing width for the selector label."""

            return len(text) * 20

        def elidedText(self, text: str, mode: object, width: int) -> str:
            """Record elision inputs and return a deterministic label."""

            calls.append((text, mode, width))
            return "Scene..."

    mode = object()

    assert (
        selector_display_text_for_metrics(
            "Scene With Long Name",
            font_metrics=_Metrics(),
            text_elide_mode=mode,
            max_width=120,
            horizontal_padding=24,
        )
        == "Scene..."
    )
    assert calls == [("Scene With Long Name", mode, 96)]


def test_selector_width_for_metrics_text_uses_host_metrics() -> None:
    """Selector width calculation should combine metrics, padding, and bounds."""

    class _Metrics:
        """Provide host-like text width measurement."""

        def horizontalAdvance(self, text: str) -> int:
            """Return deterministic text width."""

            return len(text) * 10

    assert (
        selector_width_for_metrics_text(
            "Wide",
            font_metrics=_Metrics(),
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 68
    )


def test_selector_width_for_widget_text_uses_widget_metrics() -> None:
    """Selector widget adapter should measure text without a widget host wrapper."""

    class _Metrics:
        """Provide host-like text width measurement."""

        def horizontalAdvance(self, text: str) -> int:
            """Return deterministic text width."""

            return len(text) * 10

    class _Widget:
        """Provide host-like font metrics."""

        def fontMetrics(self) -> _Metrics:
            """Return deterministic font metrics."""

            return _Metrics()

    assert (
        selector_width_for_widget_text(
            "Wide",
            widget=_Widget(),
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 68
    )


def test_selector_current_width_prefers_settled_widget_width() -> None:
    """Selector current width should use live widget width once it is settled."""

    class _Widget:
        """Provide host-like width measurement."""

        def width(self) -> int:
            """Return a settled widget width."""

            return 144

    assert (
        selector_current_width(
            _Widget(),
            minimum_width=58,
            fallback_width=92,
        )
        == 144
    )


def test_selector_current_width_uses_fallback_until_widget_settles() -> None:
    """Selector current width should use fallback width for minimum-sized widgets."""

    class _Widget:
        """Provide host-like width measurement."""

        def width(self) -> int:
            """Return an unsettled widget width."""

            return 40

    assert (
        selector_current_width(
            _Widget(),
            minimum_width=58,
            fallback_width=92,
        )
        == 92
    )


def test_scene_selector_current_width_uses_active_scene_fallback() -> None:
    """Scene selector width fallback should measure the active scene label."""

    class _Widget:
        """Provide host-like metrics and unsettled width."""

        def width(self) -> int:
            """Return an unsettled widget width."""

            return 0

        def fontMetrics(self) -> object:
            """Return text metrics for fallback measurement."""

            return _Metrics()

    class _Metrics:
        """Provide deterministic text measurement."""

        def horizontalAdvance(self, text: str) -> int:
            """Return fixed-width measurement."""

            return len(text) * 10

    scenes = (
        OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),
        OutputCanvasSceneGroup("run-2", "cafe", "Cafe", 1, ()),
    )

    assert (
        scene_selector_current_width(
            scenes,
            active_scene_key="cafe",
            active_scene_overview=False,
            widget=_Widget(),
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 68
    )


def test_source_selector_current_width_uses_active_source_fallback() -> None:
    """Source selector width fallback should measure the active source label."""

    class _Widget:
        """Provide host-like metrics and unsettled width."""

        def width(self) -> int:
            """Return an unsettled widget width."""

            return 0

        def fontMetrics(self) -> object:
            """Return text metrics for fallback measurement."""

            return _Metrics()

    class _Metrics:
        """Provide deterministic text measurement."""

        def horizontalAdvance(self, text: str) -> int:
            """Return fixed-width measurement."""

            return len(text) * 10

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert (
        source_selector_current_width(
            sources,
            active_source_key="wf:upscale",
            widget=_Widget(),
            minimum_width=58,
            maximum_width=260,
            horizontal_padding=28,
        )
        == 98
    )
