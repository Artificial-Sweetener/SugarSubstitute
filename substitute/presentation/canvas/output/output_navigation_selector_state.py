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

"""Build Output selector labels and immutable presentation state."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
    output_scene_title_text,
    output_source_label_text,
)


@dataclass(frozen=True, slots=True)
class SourceSelectorButtonState:
    """Describe source-selector button presentation state."""

    text: str
    tooltip: str
    width: int
    visible: bool


@dataclass(frozen=True, slots=True)
class SetSelectorButtonState:
    """Describe set-selector button presentation state."""

    text: str
    visible: bool


@dataclass(frozen=True, slots=True)
class SceneSelectorButtonState:
    """Describe scene-selector button presentation state."""

    text: str
    tooltip: str
    width: int
    visible: bool


def source_selector_full_text(
    sources: Iterable[OutputCanvasSourceGroup],
    *,
    active_source_key: str | None,
) -> str:
    """Return the unelided label for the collapsed source selector."""

    source_groups = {source.source_key: source for source in sources}
    if active_source_key in source_groups:
        return render_application_text(
            output_source_label_text(source_groups[active_source_key])
        )
    first_source = next(iter(source_groups.values()), None)
    if first_source is not None:
        return render_application_text(output_source_label_text(first_source))
    return render_application_text(app_text("Output"))


def source_selector_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SourceSelectorButtonState:
    """Return prepared normal source-selector presentation state."""

    return SourceSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=visible,
    )


def compare_source_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SourceSelectorButtonState:
    """Return prepared comparison source-selector presentation state."""

    return source_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )


def set_selector_button_state(
    *,
    active_set_index: int,
    visible: bool,
) -> SetSelectorButtonState:
    """Return prepared normal set-selector presentation state."""

    return SetSelectorButtonState(text=str(active_set_index), visible=visible)


def compare_set_button_state(
    *,
    set_index: int,
    visible: bool,
) -> SetSelectorButtonState:
    """Return prepared comparison set-selector presentation state."""

    return SetSelectorButtonState(text=str(set_index), visible=visible)


def scene_selector_full_text(
    scene_groups: Iterable[OutputCanvasSceneGroup],
    *,
    active_scene_key: str | None,
    active_scene_overview: bool,
) -> str:
    """Return the unelided label for the normal scene selector."""

    if active_scene_overview:
        return render_application_text(app_text("All"))
    scenes_by_key = {scene.scene_key: scene for scene in scene_groups}
    if active_scene_key in scenes_by_key:
        return render_application_text(
            output_scene_title_text(scenes_by_key[active_scene_key])
        )
    return render_application_text(app_text("All"))


def scene_selector_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SceneSelectorButtonState:
    """Return prepared normal scene-selector presentation state."""

    return SceneSelectorButtonState(
        text=display_text,
        tooltip=full_text if display_text != full_text else "",
        width=width,
        visible=visible,
    )


def compare_scene_full_text(
    scene_groups: Iterable[OutputCanvasSceneGroup],
    *,
    scene_key: str | None,
    scene_count: int,
) -> str:
    """Return the unelided label for one compare scene selector."""

    scenes_by_key = {scene.scene_key: scene for scene in scene_groups}
    if scene_count > 1 and scene_key in scenes_by_key:
        return render_application_text(
            output_scene_title_text(scenes_by_key[scene_key])
        )
    return render_application_text(app_text("All"))


def compare_scene_button_state(
    *,
    full_text: str,
    display_text: str,
    width: int,
    visible: bool,
) -> SceneSelectorButtonState:
    """Return prepared comparison scene-selector presentation state."""

    return scene_selector_button_state(
        full_text=full_text,
        display_text=display_text,
        width=width,
        visible=visible,
    )


__all__ = [
    "SceneSelectorButtonState",
    "SetSelectorButtonState",
    "SourceSelectorButtonState",
    "compare_scene_button_state",
    "compare_scene_full_text",
    "compare_set_button_state",
    "compare_source_button_state",
    "scene_selector_button_state",
    "scene_selector_full_text",
    "set_selector_button_state",
    "source_selector_button_state",
    "source_selector_full_text",
]
