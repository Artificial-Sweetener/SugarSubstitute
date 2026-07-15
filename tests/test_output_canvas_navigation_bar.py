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

"""Verify Output canvas navigation-bar construction helpers."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    SceneSelectorButtonState,
    SetSelectorButtonState,
    SourceSelectorButtonState,
    SourceTabTooltip,
    SourceTabItem,
    SourceTabTooltipRefreshItem,
    SourceTabsRebuildPlan,
    apply_compare_scene_button_state,
    apply_compare_set_button_state,
    apply_compare_source_button_state,
    apply_scene_selector_button_state,
    apply_set_selector_button_state,
    apply_source_selector_button_state,
    compare_scene_button_state,
    compare_scene_full_text,
    compare_set_button_state,
    compare_source_button_state,
    scene_selector_button_state,
    scene_selector_current_width,
    scene_selector_full_text,
    selector_display_text,
    selector_display_text_for_metrics,
    selector_font_metrics_for_widget,
    selector_current_width,
    selector_text_width,
    selector_width_for_text,
    selector_width_for_metrics_text,
    selector_width_for_widget_text,
    set_selector_button_state,
    source_selector_button_state,
    source_selector_current_width,
    source_selector_full_text,
    source_tab_items,
    source_tab_removal_keys,
    source_tab_signature,
    source_tab_tooltip,
    source_tab_tooltip_refresh_items,
    source_tabs_rebuild_plan,
    sync_comparison_navigation_buttons,
)


class _SelectorButton:
    """Record selector button presentation writes."""

    def __init__(self) -> None:
        """Create an unset fake button."""

        self.text = ""
        self.tooltip = ""
        self.fixed_width = 0
        self.visible = False

    def setText(self, text: str) -> None:
        """Record selector text."""

        self.text = text

    def setToolTip(self, tooltip: str) -> None:
        """Record selector tooltip."""

        self.tooltip = tooltip

    def setFixedWidth(self, width: int) -> None:
        """Record selector fixed width."""

        self.fixed_width = width

    def setVisible(self, visible: bool) -> None:
        """Record selector visibility."""

        self.visible = visible


class _Container:
    """Record container visibility mutations."""

    def __init__(self) -> None:
        """Create a visible fake container."""

        self.hidden = False

    def hide(self) -> None:
        """Record that the container was hidden."""

        self.hidden = True


def test_source_tab_signature_uses_source_keys_and_labels() -> None:
    """Source-tab signatures should track only tab identity values."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert source_tab_signature(sources) == (
        ("wf:text", "Text"),
        ("wf:upscale", "Upscale"),
    )


def test_source_tab_signature_preserves_order() -> None:
    """Source-tab signatures should preserve visible source order."""

    sources = (
        OutputCanvasSourceGroup("wf:second", "Second", {}),
        OutputCanvasSourceGroup("wf:first", "First", {}),
    )

    assert source_tab_signature(sources) == (
        ("wf:second", "Second"),
        ("wf:first", "First"),
    )


def test_source_tabs_rebuild_plan_rebuilds_for_changed_signature() -> None:
    """Source-tab rebuild plans should request rebuilds for changed identities."""

    sources = (
        OutputCanvasSourceGroup("wf:text", "Text", {}),
        OutputCanvasSourceGroup("wf:upscale", "Upscale", {}),
    )

    assert source_tabs_rebuild_plan(
        sources,
        cached_signature=(("wf:text", "Text"),),
        active_source_key="wf:upscale",
    ) == SourceTabsRebuildPlan(
        signature=(("wf:text", "Text"), ("wf:upscale", "Upscale")),
        rebuild_required=True,
        active_source_key="wf:upscale",
    )


def test_source_tabs_rebuild_plan_skips_matching_signature() -> None:
    """Source-tab rebuild plans should preserve cached tabbar identities."""

    sources = (OutputCanvasSourceGroup("wf:text", "Text", {}),)

    assert source_tabs_rebuild_plan(
        sources,
        cached_signature=(("wf:text", "Text"),),
        active_source_key=None,
    ) == SourceTabsRebuildPlan(
        signature=(("wf:text", "Text"),),
        rebuild_required=False,
        active_source_key=None,
    )


def test_source_tab_items_preserve_visible_source_order() -> None:
    """Source-tab item plans should preserve tab ids, labels, and source DTOs."""

    text_source = OutputCanvasSourceGroup("wf:text", "Text", {})
    upscale_source = OutputCanvasSourceGroup("wf:upscale", "Upscale", {})

    assert source_tab_items((text_source, upscale_source)) == (
        SourceTabItem("wf:text", "Text", text_source),
        SourceTabItem("wf:upscale", "Upscale", upscale_source),
    )


def test_source_tab_removal_keys_preserve_existing_tab_order() -> None:
    """Source-tab removal plans should snapshot existing tab keys in order."""

    assert source_tab_removal_keys(
        {
            "wf:text": object(),
            "wf:upscale": object(),
            "wf:detail": object(),
        }
    ) == ("wf:text", "wf:upscale", "wf:detail")


def test_source_tab_tooltip_uses_active_set_metadata() -> None:
    """Source-tab tooltip plans should use the selected set's metadata."""

    source = OutputCanvasSourceGroup(
        "wf:text",
        "Text",
        {
            1: _image_item(width=512, height=512, duration_ms=1.0, set_index=1),
            3: _image_item(width=1024, height=768, duration_ms=3080.0, set_index=3),
        },
    )

    assert source_tab_tooltip(source, active_set_index=3) == SourceTabTooltip(
        source_key="wf:text",
        text="1024x768\n3.1s",
        installs_hover_filter=True,
    )


def test_source_tab_tooltip_skips_hover_filter_without_display_text() -> None:
    """Source-tab tooltip plans should avoid hover filters without useful text."""

    source = OutputCanvasSourceGroup(
        "wf:text",
        "Text",
        {1: _image_item(width=None, height=None, duration_ms=None, set_index=1)},
    )

    assert source_tab_tooltip(source, active_set_index=1) == SourceTabTooltip(
        source_key="wf:text",
        text="",
        installs_hover_filter=False,
    )


def test_source_tab_tooltip_refresh_items_skip_missing_tabs() -> None:
    """Source-tab tooltip refresh plans should include only existing tab widgets."""

    text_source = OutputCanvasSourceGroup("wf:text", "Text", {})
    upscale_source = OutputCanvasSourceGroup("wf:upscale", "Upscale", {})
    text_tab = object()

    assert source_tab_tooltip_refresh_items(
        (text_source, upscale_source),
        {"wf:text": text_tab},
    ) == (
        SourceTabTooltipRefreshItem(
            source_key="wf:text",
            source=text_source,
            tab_item=text_tab,
        ),
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


def test_source_selector_button_state_sets_tooltip_for_elided_text() -> None:
    """Collapsed source selector state should expose full labels as tooltips."""

    assert source_selector_button_state(
        full_text="Very long source label",
        display_text="Very long...",
        width=260,
        source_tabs_collapsed=True,
        tab_count=2,
        active_scene_overview=False,
    ) == SourceSelectorButtonState(
        text="Very long...",
        tooltip="Very long source label",
        width=260,
        visible=True,
    )


def test_source_selector_button_state_hides_when_expanded_or_single_tab() -> None:
    """Collapsed source selector state should hide outside compact multi-tab mode."""

    assert (
        source_selector_button_state(
            full_text="Text",
            display_text="Text",
            width=58,
            source_tabs_collapsed=False,
            tab_count=2,
            active_scene_overview=False,
        ).visible
        is False
    )
    assert (
        source_selector_button_state(
            full_text="Text",
            display_text="Text",
            width=58,
            source_tabs_collapsed=True,
            tab_count=1,
            active_scene_overview=False,
        ).visible
        is False
    )
    assert (
        source_selector_button_state(
            full_text="Text",
            display_text="Text",
            width=58,
            source_tabs_collapsed=True,
            tab_count=2,
            active_scene_overview=True,
        ).visible
        is False
    )


def test_compare_source_button_state_sets_tooltip_for_elided_text() -> None:
    """Compare source selector state should expose full labels as tooltips."""

    assert compare_source_button_state(
        full_text="Very long comparison source",
        display_text="Very long...",
        width=260,
    ) == SourceSelectorButtonState(
        text="Very long...",
        tooltip="Very long comparison source",
        width=260,
        visible=True,
    )


def test_compare_source_button_state_stays_visible_without_tooltip() -> None:
    """Compare source selector state should always keep the compare source visible."""

    assert compare_source_button_state(
        full_text="Text",
        display_text="Text",
        width=58,
    ) == SourceSelectorButtonState(
        text="Text",
        tooltip="",
        width=58,
        visible=True,
    )


def test_apply_source_selector_button_state_updates_button() -> None:
    """Source selector adapter should apply text, tooltip, width, and visibility."""

    button = _SelectorButton()

    button_state = apply_source_selector_button_state(
        button,
        full_text="Primary Source",
        display_text="Primary...",
        width=96,
        source_tabs_collapsed=True,
        tab_count=3,
        active_scene_overview=False,
    )

    assert button_state == SourceSelectorButtonState(
        text="Primary...",
        tooltip="Primary Source",
        width=96,
        visible=True,
    )
    assert button.text == "Primary..."
    assert button.tooltip == "Primary Source"
    assert button.fixed_width == 96
    assert button.visible is True


def test_apply_compare_source_button_state_updates_button() -> None:
    """Compare source adapter should apply text, tooltip, width, and visibility."""

    button = _SelectorButton()

    button_state = apply_compare_source_button_state(
        button,
        full_text="Comparison Source",
        display_text="Comparison...",
        width=124,
    )

    assert button_state == SourceSelectorButtonState(
        text="Comparison...",
        tooltip="Comparison Source",
        width=124,
        visible=True,
    )
    assert button.text == "Comparison..."
    assert button.tooltip == "Comparison Source"
    assert button.fixed_width == 124
    assert button.visible is True


def test_set_selector_button_state_shows_active_set_for_multi_set_outputs() -> None:
    """Set selector state should show the active set when multiple sets exist."""

    assert set_selector_button_state(
        active_set_index=3,
        active_scene_overview=False,
        set_count=4,
        grid_available=False,
    ) == SetSelectorButtonState(text="3", visible=True)


def test_apply_set_selector_button_state_updates_button() -> None:
    """Set selector adapter should apply text and visibility to the host button."""

    button = _SelectorButton()

    button_state = apply_set_selector_button_state(
        button,
        active_set_index=2,
        active_scene_overview=False,
        set_count=3,
        grid_available=False,
    )

    assert button_state == SetSelectorButtonState(text="2", visible=True)
    assert button.text == "2"
    assert button.visible is True


def test_apply_scene_selector_button_state_updates_button() -> None:
    """Scene selector adapter should apply text, tooltip, width, and visibility."""

    button = _SelectorButton()

    button_state = apply_scene_selector_button_state(
        button,
        full_text="Wide Scene",
        display_text="Wide...",
        width=84,
        scene_count=2,
    )

    assert button_state == SceneSelectorButtonState(
        text="Wide...",
        tooltip="Wide Scene",
        width=84,
        visible=True,
    )
    assert button.text == "Wide..."
    assert button.tooltip == "Wide Scene"
    assert button.fixed_width == 84
    assert button.visible is True


def test_set_selector_button_state_shows_for_grid_available_single_set() -> None:
    """Set selector state should show set zero access when a source grid exists."""

    assert set_selector_button_state(
        active_set_index=1,
        active_scene_overview=False,
        set_count=1,
        grid_available=True,
    ) == SetSelectorButtonState(text="1", visible=True)


def test_set_selector_button_state_hides_for_scene_overview_or_single_output() -> None:
    """Set selector state should hide outside set or grid navigation contexts."""

    assert (
        set_selector_button_state(
            active_set_index=2,
            active_scene_overview=True,
            set_count=3,
            grid_available=True,
        ).visible
        is False
    )
    assert (
        set_selector_button_state(
            active_set_index=1,
            active_scene_overview=False,
            set_count=1,
            grid_available=False,
        ).visible
        is False
    )


def test_compare_set_button_state_shows_set_when_multiple_sets_exist() -> None:
    """Compare set selector state should show when comparison has multiple sets."""

    assert compare_set_button_state(set_index=4, set_count=5) == SetSelectorButtonState(
        text="4",
        visible=True,
    )


def test_apply_compare_set_button_state_updates_button() -> None:
    """Compare set adapter should apply text and visibility to the host button."""

    button = _SelectorButton()

    button_state = apply_compare_set_button_state(
        button,
        set_index=3,
        set_count=4,
    )

    assert button_state == SetSelectorButtonState(text="3", visible=True)
    assert button.text == "3"
    assert button.visible is True


def test_sync_comparison_navigation_buttons_hides_container_when_not_visible() -> None:
    """Comparison navigation sync should hide the container without a comparison."""

    container = _Container()
    calls: list[tuple[str, object, object]] = []

    refreshed = sync_comparison_navigation_buttons(
        comparison_nav_container=container,
        enabled=True,
        comparison_selection=None,
        scene_button=object(),
        set_button=object(),
        source_button=object(),
        sync_scene_button=lambda button, selection: calls.append(
            ("scene", button, selection)
        ),
        sync_set_button=lambda button, selection: calls.append(
            ("set", button, selection)
        ),
        sync_source_button=lambda button, selection: calls.append(
            ("source", button, selection)
        ),
    )

    assert refreshed is False
    assert container.hidden is True
    assert calls == []


def test_sync_comparison_navigation_buttons_refreshes_each_selector() -> None:
    """Comparison navigation sync should refresh scene, set, and source selectors."""

    container = _Container()
    selection = object()
    scene_button = object()
    set_button = object()
    source_button = object()
    calls: list[tuple[str, object, object]] = []

    refreshed = sync_comparison_navigation_buttons(
        comparison_nav_container=container,
        enabled=True,
        comparison_selection=selection,
        scene_button=scene_button,
        set_button=set_button,
        source_button=source_button,
        sync_scene_button=lambda button, selected: calls.append(
            ("scene", button, selected)
        ),
        sync_set_button=lambda button, selected: calls.append(
            ("set", button, selected)
        ),
        sync_source_button=lambda button, selected: calls.append(
            ("source", button, selected)
        ),
    )

    assert refreshed is True
    assert container.hidden is False
    assert calls == [
        ("scene", scene_button, selection),
        ("set", set_button, selection),
        ("source", source_button, selection),
    ]


def test_compare_set_button_state_hides_for_single_set() -> None:
    """Compare set selector state should hide without an alternate set choice."""

    assert compare_set_button_state(set_index=1, set_count=1) == SetSelectorButtonState(
        text="1",
        visible=False,
    )


def test_compare_scene_full_text_uses_selected_scene_title() -> None:
    """Compare scene labels should use the selected concrete scene title."""

    scenes = (
        OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),
        OutputCanvasSceneGroup("run-2", "cafe", "Cafe", 1, ()),
    )

    assert (
        compare_scene_full_text(scenes, scene_key="portrait", scene_count=2)
        == "Portrait"
    )


def test_compare_scene_full_text_uses_all_without_scene_choice() -> None:
    """Compare scene labels should use All when no concrete scene is available."""

    scenes = (OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),)

    assert compare_scene_full_text(scenes, scene_key="portrait", scene_count=1) == "All"
    assert compare_scene_full_text(scenes, scene_key="missing", scene_count=2) == "All"


def test_compare_scene_button_state_sets_tooltip_for_elided_text() -> None:
    """Compare scene selector state should expose full labels as tooltips."""

    assert compare_scene_button_state(
        full_text="Very long comparison scene",
        display_text="Very long...",
        width=260,
        scene_count=2,
    ) == SceneSelectorButtonState(
        text="Very long...",
        tooltip="Very long comparison scene",
        width=260,
        visible=True,
    )


def test_apply_compare_scene_button_state_updates_button() -> None:
    """Compare scene adapter should apply text, tooltip, width, and visibility."""

    button = _SelectorButton()

    button_state = apply_compare_scene_button_state(
        button,
        full_text="Comparison Scene",
        display_text="Comparison...",
        width=112,
        scene_count=3,
    )

    assert button_state == SceneSelectorButtonState(
        text="Comparison...",
        tooltip="Comparison Scene",
        width=112,
        visible=True,
    )
    assert button.text == "Comparison..."
    assert button.tooltip == "Comparison Scene"
    assert button.fixed_width == 112
    assert button.visible is True


def test_compare_scene_button_state_hides_for_single_scene() -> None:
    """Compare scene selector state should hide without multiple scenes."""

    assert compare_scene_button_state(
        full_text="All",
        display_text="All",
        width=58,
        scene_count=1,
    ) == SceneSelectorButtonState(
        text="All",
        tooltip="",
        width=58,
        visible=False,
    )


def test_scene_selector_full_text_uses_active_scene_title() -> None:
    """Scene selector labels should prefer the active scene title."""

    scenes = (
        OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),
        OutputCanvasSceneGroup("run-2", "cafe", "Cafe", 1, ()),
    )

    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="cafe",
            active_scene_overview=False,
        )
        == "Cafe"
    )


def test_scene_selector_full_text_uses_all_for_overview_or_missing_scene() -> None:
    """Scene selector labels should use All outside a concrete scene."""

    scenes = (OutputCanvasSceneGroup("run-1", "portrait", "Portrait", 0, ()),)

    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="portrait",
            active_scene_overview=True,
        )
        == "All"
    )
    assert (
        scene_selector_full_text(
            scenes,
            active_scene_key="missing",
            active_scene_overview=False,
        )
        == "All"
    )


def test_scene_selector_button_state_sets_tooltip_for_elided_text() -> None:
    """Scene selector state should expose full labels as tooltips."""

    assert scene_selector_button_state(
        full_text="Very long scene title",
        display_text="Very long...",
        width=260,
        scene_count=3,
    ) == SceneSelectorButtonState(
        text="Very long...",
        tooltip="Very long scene title",
        width=260,
        visible=True,
    )


def test_scene_selector_button_state_hides_for_single_scene_without_tooltip() -> None:
    """Scene selector state should hide when there is no scene choice."""

    assert scene_selector_button_state(
        full_text="Portrait",
        display_text="Portrait",
        width=92,
        scene_count=1,
    ) == SceneSelectorButtonState(
        text="Portrait",
        tooltip="",
        width=92,
        visible=False,
    )


def _image_item(
    *,
    width: int | None,
    height: int | None,
    duration_ms: float | None,
    set_index: int,
) -> OutputCanvasImageItem:
    """Return a projection item with tooltip-relevant metadata."""

    return OutputCanvasImageItem(
        uuid4(),
        ImageMeta(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=set_index,
            suffix="",
            path=f"C:\\outputs\\image-{set_index}.png",
            width=width,
            height=height,
            list_index=set_index - 1,
            cube_execution_duration_ms=duration_ms,
        ),
        set_index,
    )
