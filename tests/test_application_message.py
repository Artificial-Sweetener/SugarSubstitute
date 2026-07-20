#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Tests for GUI-independent application message rendering."""

from __future__ import annotations

from sugarsubstitute_shared.localization import (
    app_text,
    render_source_application_text,
)


def test_source_renderer_interpolates_nested_application_messages() -> None:
    """English rendering should preserve opaque values and expand nested copy."""

    message = app_text(
        "%1 — %2",
        app_text("Missing %1", "モジュール"),
        "用户输入",
    )

    assert render_source_application_text(message) == ("Missing モジュール — 用户输入")


def test_source_renderer_replaces_double_digit_placeholders_safely() -> None:
    """Descending replacement should not corrupt placeholders above nine."""

    message = app_text(
        "%10 %1",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
    )

    assert render_source_application_text(message) == "ten one"


def test_source_renderer_preserves_opaque_authored_text() -> None:
    """Unmarked authored text should pass through exactly as supplied."""

    authored = "  作者のキューブ名 / 用户节点  "

    assert render_source_application_text(authored) == authored
