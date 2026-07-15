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

"""Contract tests for the embedded ComfyUI Settings webview helpers."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from substitute.domain.onboarding import ComfyEndpoint
from substitute.presentation.shell import comfy_settings_webview
from substitute.presentation.shell.comfy_settings_webview import (
    ComfySettingsAccentPalette,
    ComfySettingsWebViewRequest,
    build_comfy_settings_bootstrap_script,
    build_comfy_settings_dialog_focus_script,
    comfy_settings_accent_palette,
    comfy_settings_window_geometry,
)


def test_comfy_settings_webview_request_uses_endpoint_root_url() -> None:
    """The settings webview should load ComfyUI's frontend root."""

    request = ComfySettingsWebViewRequest(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
    )

    assert request.url() == "http://127.0.0.1:8188/"


def test_comfy_settings_window_geometry_centers_over_anchor() -> None:
    """The WebEngine window should position independently over the main window."""

    anchor = QRect(100, 80, 1400, 900)

    geometry = comfy_settings_window_geometry(anchor)

    assert geometry.center() == anchor.center()
    assert geometry.width() == 1180
    assert geometry.height() == 810


def test_comfy_settings_css_waits_for_open_dialog_before_suppressing_workspace() -> (
    None
):
    """The injected CSS should preserve startup and isolate the opened dialog."""

    script = build_comfy_settings_dialog_focus_script()

    assert ".sugar-comfy-settings-dialog-mask" in script
    assert ".sugar-comfy-settings-dialog-frame" in script
    assert ".sugar-comfy-settings-dialog-content" in script
    assert "background: #111" in script
    assert "height: 100vh" in script
    assert "width: 100vw" in script
    assert '[data-component-id="LeftPanelHeader"]' in script
    assert ".sugar-comfy-settings-hidden-header" in script
    assert ".graph-canvas-container" not in script
    assert ":has(" not in script


def test_comfy_settings_accent_palette_derives_tokens_from_accent_color() -> None:
    """The settings CSS palette should derive its tokens from the app accent."""

    palette = comfy_settings_accent_palette(QColor("#E91E63"))

    assert palette.primary == "#E91E63"
    assert palette.soft_background == "rgba(233, 30, 99, 0.18)"
    assert palette.hover != palette.primary
    assert palette.active != palette.primary
    assert palette.soft_foreground.startswith("#")
    assert palette.contrast == "#FFFFFF"


def test_comfy_settings_accent_palette_uses_theme_derived_qfluent_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The webview should use QFluent's theme-adjusted accent token."""

    monkeypatch.setattr(
        comfy_settings_webview,
        "themeColor",
        lambda: QColor("#FF63B4"),
    )

    palette = comfy_settings_accent_palette()

    assert palette.primary == "#FF63B4"


def test_comfy_settings_css_overrides_comfy_primevue_accent_tokens() -> None:
    """The injected CSS should recolor Comfy controls through scoped theme tokens."""

    script = build_comfy_settings_dialog_focus_script(
        accent_palette=ComfySettingsAccentPalette(
            primary="#AA3366",
            hover="#BB4477",
            active="#CC5588",
            soft_background="rgba(170, 51, 102, 0.18)",
            soft_foreground="#DD77AA",
            contrast="#FFFFFF",
        ),
    )

    assert "--sugar-comfy-settings-accent: #AA3366" in script
    assert "--p-primary-color: var(--sugar-comfy-settings-accent)" in script
    assert "--p-primary-hover-color: var(--sugar-comfy-settings-accent-hover)" in script
    assert "--p-button-primary-background: var(--sugar-comfy-settings-accent)" in script
    assert (
        "--p-tag-primary-background: var(--sugar-comfy-settings-accent-soft)" in script
    )
    assert (
        "--p-tag-primary-color: var(--sugar-comfy-settings-accent-foreground)" in script
    )
    assert (
        "--p-radiobutton-checked-background: var(--sugar-comfy-settings-accent)"
        in script
    )
    assert (
        "--p-radiobutton-icon-checked-color: "
        "var(--sugar-comfy-settings-accent-contrast)"
    ) in script
    assert "transition: none !important" in script
    assert (
        "--p-toggleswitch-checked-background: var(--sugar-comfy-settings-accent)"
    ) in script
    assert "--p-slider-range-background: var(--sugar-comfy-settings-accent)" in script
    assert ".p-tag.p-component" in script
    assert ".p-radiobutton.p-radiobutton-checked" in script
    assert ".p-toggleswitch.p-toggleswitch-checked" in script
    assert ".p-slider-range" in script


def test_comfy_settings_bootstrap_resolves_bundled_dialog_service() -> None:
    """The bootstrap should discover and call Comfy's settings dialog composable."""

    script = build_comfy_settings_bootstrap_script()

    assert "dialogService-" in script
    assert "useSettingsDialog as" in script
    assert "fetch(moduleUrl" in script
    assert "import(moduleUrl)" in script
    assert 'const targetPanel = "root/Comfy"' in script
    assert 'const targetSettingId = "Comfy.VueNodes.Enabled"' in script
    assert "useSettingsDialog().show(undefined, targetSettingId)" in script
    assert "selectTargetSettingsCategory" in script
    assert '[data-nav-id="${targetPanel}"]' in script
    assert "waitForTargetSettingsContent" in script
    assert "CSS.escape(targetSettingId)" in script
    assert '[data-testid="settings-dialog"]' in script
    assert "closest('.p-dialog-content, [data-pc-section=\"content\"]')" in script
    assert "closest('.p-dialog-mask')" in script
    assert "focusSettingsDialog" in script
    assert "applySettingsAccent" in script
    assert "const accentTokens" in script
    assert 'settingsRoot.style.setProperty(name, value, "important")' in script
    assert (
        'radioBox.style.setProperty("background-color", '
        'accentTokens["--sugar-comfy-settings-accent"], "important")'
    ) in script
    assert (
        'radioIcon.style.setProperty("background-color", '
        'accentTokens["--sugar-comfy-settings-accent-contrast"], "important")'
    ) in script
    assert 'radioBox.style.setProperty("transition", "none", "important")' in script
    assert 'radio.style.setProperty("--p-radiobutton-checked-background"' in script
    assert (
        'slider.style.setProperty("background-color", '
        'accentTokens["--sugar-comfy-settings-accent"], "important")'
    ) in script
    assert (
        'range.style.setProperty("background-color", '
        'accentTokens["--sugar-comfy-settings-accent"], "important")'
    ) in script
    assert "hideSettingsCloseControls" in script
    assert "hideSettingsReservedHeaders" in script
    assert "alignSettingsSearchWithContent" in script
    assert 'style.setProperty("padding-top"' in script
    assert 'style.setProperty("margin-top"' in script
    assert "dataset.sugarBasePaddingTop" in script
    assert "dataset.sugarBaseMarginTop" in script
    assert "searchInput.getBoundingClientRect().top" in script
    assert 'style.setProperty("padding-left"' not in script
    assert 'style.setProperty("padding-right"' not in script
    assert 'control.closest("header")' in script
    assert (
        "header.flex.h-18.w-full.shrink-0.items-center-safe.gap-2.pr-3.pl-6" in script
    )
    assert "sugar-comfy-settings-hidden-close" in script
    assert "sugar-comfy-settings-dialog-opened" in script
