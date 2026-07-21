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

"""Validate rendered text retention throughout regular prompt pointer reorders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QImage

from .action_driver import dispatch_action
from .backing_store_capture import capture_editor_backing_store
from .glyph_visual_match import fragment_has_expected_pixels
from .models import PromptAbuseAction, PromptAbuseScenario
from .real_shell_mount import (
    create_prompt_abuse_real_shell_harness,
    prepare_prompt_abuse_real_shell_mount,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_cache import (
    translated_snapshot_offset,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderTextPaintFragment,
)
from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionTextFragment,
)

_VISUAL_SCENARIOS = frozenset(
    {
        "long-decorated-pointer-reorder-visibility",
        "long-wrapped-cross-line-pointer-reorder-visibility",
        "max-span-pointer-reorder-preview-visibility",
        "scene-partition-pointer-reorder-visibility",
        "scene-marker-alt-release-retention",
    }
)
_MINIMUM_RETAINED_TEXT_RATIO = 0.75


@dataclass(frozen=True, slots=True)
class _ExpectedChipText:
    """Describe expected viewport-local text for one visible reorder chip."""

    segment_index: int
    fragments: tuple[PromptReorderTextPaintFragment, ...]
    translation: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class _CapturedEditorFrame:
    """Pair one real backing-store image with its animation ownership state."""

    image: QImage
    reorder_animation_active: bool


def capture_prompt_reorder_visual_violations(
    scenario: PromptAbuseScenario,
    *,
    artifact_root: Path,
) -> tuple[str, ...]:
    """Replay selected prompt reorders and reject disappearing rendered text."""

    if scenario.name not in _VISUAL_SCENARIOS:
        return ()
    harness = create_prompt_abuse_real_shell_harness(
        scenario,
        artifact_root=artifact_root,
    )
    violations: list[str] = []
    try:
        mounted = prepare_prompt_abuse_real_shell_mount(
            harness,
            scenario,
            alias=f"visual-{scenario.name}",
        )
        editor = mounted.field.editor
        baseline_frame = _capture_editor_backing_store(editor)
        if baseline_frame is None:
            return ("reorder_backing_store_capture_unavailable:baseline",)
        baseline_image = baseline_frame.image
        baseline_text_pixels = _neutral_bright_viewport_pixels(editor, baseline_image)
        for action_index, action in enumerate(scenario.actions):
            dispatch_action(
                mounted.action_host,
                editor,
                mounted.target,
                action,
                action_index=action_index,
            )
            if not _is_visual_checkpoint(action_index, action):
                continue
            frame = _capture_editor_backing_store(editor)
            if frame is None:
                violations.append(
                    f"reorder_backing_store_capture_unavailable:action={action_index}"
                )
                continue
            image = frame.image
            text_pixels = _neutral_bright_viewport_pixels(editor, image)
            missing_chip_text = (
                ()
                if frame.reorder_animation_active
                else _missing_reorder_chip_text(editor, image)
            )
            missing_scene_titles = _missing_scene_title_text(editor, image)
            minimum_pixels = round(baseline_text_pixels * _MINIMUM_RETAINED_TEXT_RATIO)
            if text_pixels < minimum_pixels:
                violations.append(
                    "reorder_rendered_text_loss:"
                    f"action={action_index}:pixels={text_pixels}:"
                    f"baseline={baseline_text_pixels}"
                )
            if missing_chip_text:
                violations.append(
                    "reorder_rendered_chip_text_missing:"
                    f"action={action_index}:indices={missing_chip_text!r}"
                )
            if missing_scene_titles:
                violations.append(
                    "reorder_rendered_scene_title_missing:"
                    f"action={action_index}:runs={missing_scene_titles!r}"
                )
            if (
                text_pixels >= minimum_pixels
                and not missing_chip_text
                and not missing_scene_titles
            ):
                continue
            failure_path = artifact_root / (
                f"{scenario.name}-action-{action_index}-text-loss.png"
            )
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(failure_path))
    finally:
        harness.close()
    return tuple(dict.fromkeys(violations))


def _is_visual_checkpoint(action_index: int, action: PromptAbuseAction) -> bool:
    """Return whether one replay action can expose transient text loss."""

    return bool(
        action_index == 1
        or action.kind
        in {
            "reorder_drag_threshold",
            "reorder_drag_move",
            "reorder_drag_release",
        }
        or (action.kind == "key_release" and action.value == "alt")
    )


def _capture_editor_backing_store(editor: object) -> _CapturedEditorFrame | None:
    """Capture queued production paint without forcing an artificial full render."""

    prompt_editor = cast(Any, editor)
    reorder_animation_active = _reorder_animation_active(prompt_editor)
    image = capture_editor_backing_store(prompt_editor, event_cycles=4)
    if image is None:
        return None
    return _CapturedEditorFrame(
        image=image,
        reorder_animation_active=reorder_animation_active,
    )


def _reorder_animation_active(editor: Any) -> bool:
    """Return whether overlay geometry is moving relative to its last painted frame."""

    overlay = editor._segment_overlay
    if overlay is None:
        return False
    return bool(
        overlay._animation_presenter.is_animating()
        or overlay._held_chip_presenter.paint_rect_overrides()
    )


def _neutral_bright_viewport_pixels(editor: object, image: QImage) -> int:
    """Count sampled light text pixels while excluding saturated chip chrome."""

    prompt_editor = cast(Any, editor)
    viewport = prompt_editor.viewport()
    origin = viewport.mapTo(prompt_editor, QPoint(0, 0))
    left = max(0, origin.x())
    top = max(0, origin.y())
    right = min(image.width(), left + viewport.width())
    bottom = min(image.height(), top + viewport.height())
    count = 0
    for y in range(top, bottom, 2):
        for x in range(left, right, 2):
            color = image.pixelColor(x, y)
            red = color.red()
            green = color.green()
            blue = color.blue()
            if (
                min(red, green, blue) >= 140
                and max(red, green, blue)
                - min(
                    red,
                    green,
                    blue,
                )
                <= 55
            ):
                count += 1
    return count


def _missing_reorder_chip_text(editor: object, image: QImage) -> tuple[int, ...]:
    """Return visible chips lacking their own expected rendered text pixels."""

    prompt_editor = cast(Any, editor)
    viewport = prompt_editor.viewport()
    viewport_origin = viewport.mapTo(prompt_editor, QPoint())
    visible_image_rect = QRect(viewport_origin, viewport.size()).intersected(
        image.rect()
    )
    missing: list[int] = []
    for expected_chip in _expected_reorder_chip_text(prompt_editor):
        dx, dy = expected_chip.translation
        visible_results = tuple(
            result
            for fragment in expected_chip.fragments
            if (
                result := fragment_has_expected_pixels(
                    image,
                    fragment=fragment,
                    translation=QPointF(
                        dx + viewport_origin.x(),
                        dy + viewport_origin.y(),
                    ),
                    visible_image_rect=visible_image_rect,
                ),
            )
            is not None
        )
        if not visible_results or any(visible_results):
            continue
        missing.append(expected_chip.segment_index)
    return tuple(missing)


def _missing_scene_title_text(editor: object, image: QImage) -> tuple[str, ...]:
    """Return visible semantic scene-title runs lacking their expected glyphs."""

    prompt_editor = cast(Any, editor)
    if prompt_editor._segment_overlay is not None:
        return ()
    surface = prompt_editor._surface
    preview_layout = surface._reorder_preview_projection.preview_layout
    layout = surface._layout if preview_layout is None else preview_layout
    scene_run_ids = {
        run.run_id
        for run in layout.projection_document.runs
        if run.text_style_variant in {"scene_title", "scene_error"}
        and run.display_text.strip()
    }
    if not scene_run_ids:
        return ()
    viewport = prompt_editor.viewport()
    viewport_origin = viewport.mapTo(prompt_editor, QPoint())
    visible_image_rect = QRect(viewport_origin, viewport.size()).intersected(
        image.rect()
    )
    scroll_offset = float(surface._scroll_offset())
    fragments_by_run: dict[str, list[PromptProjectionTextFragment]] = {
        run_id: [] for run_id in scene_run_ids
    }
    for line in layout._snapshot.lines:
        for fragment in line.fragments:
            if (
                isinstance(fragment, PromptProjectionTextFragment)
                and fragment.run_id in fragments_by_run
                and fragment.text.strip()
            ):
                fragments_by_run[fragment.run_id].append(fragment)

    missing: list[str] = []
    for run_id, fragments in fragments_by_run.items():
        visible_results: list[bool] = []
        for fragment in fragments:
            expected_fragment = PromptReorderTextPaintFragment(
                text=fragment.text,
                font=layout._painter.font_for_fragment(fragment),
                baseline=QPointF(
                    fragment.rect.left(), fragment.baseline - scroll_offset
                ),
                text_rect=fragment.rect.translated(0.0, -scroll_offset),
                color=layout._painter.text_color_for_fragment(fragment),
            )
            result = fragment_has_expected_pixels(
                image,
                fragment=expected_fragment,
                translation=QPointF(viewport_origin),
                visible_image_rect=visible_image_rect,
            )
            if result is not None:
                visible_results.append(result)
        if visible_results and not any(visible_results):
            missing.append(run_id)
    return tuple(sorted(missing))


def _expected_reorder_chip_text(editor: Any) -> tuple[_ExpectedChipText, ...]:
    """Return per-chip text expectations from the active production projection."""

    overlay = editor._segment_overlay
    if overlay is None:
        return ()
    state = overlay._view.render_state
    overlay_chips = state.preview_chips if state.preview_active else state.live_chips
    overlay_chips_by_index = {chip.segment_index: chip for chip in overlay_chips}
    projection_snapshots = _all_projection_chip_snapshots(editor, overlay)
    expectations: list[_ExpectedChipText] = []
    for segment_index, projection_snapshot in projection_snapshots.items():
        if segment_index == state.dragged_segment_index:
            continue
        overlay_chip = overlay_chips_by_index.get(segment_index)
        if (
            overlay_chip is not None
            and overlay_chip.owns_projection_text
            and overlay_chip.visual_snapshot is not None
            and overlay_chip.visual is not None
        ):
            dx, dy = translated_snapshot_offset(
                painted_rect=QRectF(overlay_chip.visual.hotspot_rect),
                snapshot=overlay_chip.visual_snapshot,
            )
            projection_snapshot = overlay_chip.visual_snapshot.projection_snapshot
            translation = (dx, dy)
        else:
            translation = (0.0, 0.0)
        fragments = tuple(
            fragment
            for fragment in projection_snapshot.text_fragments
            if fragment.text.strip()
        )
        if fragments:
            expectations.append(
                _ExpectedChipText(
                    segment_index=segment_index,
                    fragments=fragments,
                    translation=translation,
                )
            )
    return tuple(expectations)


def _all_projection_chip_snapshots(
    editor: Any,
    overlay: Any,
) -> dict[int, PromptReorderProjectionPaintSnapshot]:
    """Build observation-only snapshots for every chip in the active projection."""

    preview_snapshot = overlay._preview_snapshot
    preview_geometry = overlay._preview_chip_geometry_snapshot
    if preview_snapshot is not None and preview_geometry is not None:
        return cast(
            dict[int, PromptReorderProjectionPaintSnapshot],
            editor.reorder_preview_chip_projection_paint_snapshots(
                chip_geometry_snapshot=preview_geometry,
                chip_owned_ranges_by_index=(
                    preview_snapshot.chip_owned_ranges_by_index
                ),
                chip_indices=None,
            ),
        )
    live_geometry = overlay._chip_geometry_snapshot
    if live_geometry is None:
        return {}
    return cast(
        dict[int, PromptReorderProjectionPaintSnapshot],
        editor.reorder_live_chip_projection_paint_snapshots(
            chip_geometry_snapshot=live_geometry,
            chip_owned_ranges_by_index=overlay._live_chip_owned_ranges_by_index(),
        ),
    )


__all__ = ["capture_prompt_reorder_visual_violations"]
