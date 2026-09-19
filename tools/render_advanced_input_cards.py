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

"""Render production advanced-input node cards from a captured real cube."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]  # noqa: E402

from substitute.presentation.editor.panel.node_card.action_menu import (  # noqa: E402
    NodeCardActionMenuButton,
)
from substitute.presentation.editor.panel.node_card.accordion_motion import (  # noqa: E402
    AccordionMotionController,
)
from substitute.presentation.editor.panel.node_card.body_layout import (  # noqa: E402
    CardBodyLayoutState,
)
from substitute.presentation.widgets.qfluent_menu_renderer import (  # noqa: E402
    QFluentMenuRenderer,
)
from tools.editor_projection_rig.fixtures import read_json  # noqa: E402
from tools.editor_projection_rig.production_trace import (  # noqa: E402
    _build_editor_panel,
    _build_trace_shell,
    _drain_qt_events,
    _workflow_from_fixture,
)
from tools.editor_projection_rig.qt_harness import (  # noqa: E402
    create_hidden_host,
    ensure_qapplication,
)
from tools.editor_projection_rig.trace_events import (  # noqa: E402
    ProjectionTraceRecorder,
)

_FIXTURE_PATH = Path(
    "artifacts/editor_projection_rig/fixtures/workflow_sdxl_baseline.json"
)
_CUBE_ALIAS = "Cube 2: SDXL/Diffusion Upscale"
_NODE_NAME = "vae_decode_options"
_NORMAL_FIELD = "use_tiling"
_ADVANCED_FIELDS = frozenset(
    {"overlap", "temporal_overlap", "temporal_size", "tile_size"}
)
_RENDER_CARD_WIDTH = 420


@dataclass(slots=True)
class _MountedCard:
    """Own one real projected workflow and its selected production card."""

    host: QWidget
    panel: QWidget
    wrapper: QWidget

    def close(self) -> None:
        """Release the hidden Qt hierarchy after one rendered scenario."""

        self.host.close()
        self.host.deleteLater()
        _drain_qt_events(25)


def render_advanced_input_cards(output_dir: Path) -> tuple[Path, ...]:
    """Render representative light and dark disclosure states to PNG files."""

    application = ensure_qapplication()
    _register_headless_fluent_font()
    application.setProperty("substitute.reduce_motion", True)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_paths: list[Path] = []
    scenarios = (
        (Theme.LIGHT, "light-mixed-hidden", "hidden"),
        (Theme.LIGHT, "light-mixed-shown-grouped", "shown"),
        (Theme.DARK, "dark-mixed-hidden", "hidden"),
        (Theme.DARK, "dark-mixed-shown-grouped", "shown"),
        (Theme.LIGHT, "light-all-advanced-hidden", "all_advanced_hidden"),
        (Theme.LIGHT, "light-all-advanced-shown", "all_advanced"),
        (Theme.DARK, "dark-collapsed", "collapsed"),
    )
    for theme, file_stem, state in scenarios:
        mounted = _mount_real_card(theme)
        try:
            _apply_state(mounted, state)
            output_path = output_dir / f"{file_stem}.png"
            _save_widget(mounted.wrapper, output_path, theme=theme)
            rendered_paths.append(output_path.resolve())
        finally:
            mounted.close()
    menu_card = _mount_real_card(Theme.LIGHT)
    try:
        menu_path = output_dir / "light-gear-menu-open.png"
        _save_card_with_action_menu(menu_card, menu_path, theme=Theme.LIGHT)
        rendered_paths.append(menu_path.resolve())
    finally:
        menu_card.close()
    return tuple(rendered_paths)


def _register_headless_fluent_font() -> None:
    """Load Segoe UI explicitly for Qt's isolated offscreen font database."""

    windows_root = os.environ.get("WINDIR")
    if not windows_root:
        raise RuntimeError("WINDIR is required for headless Fluent rendering")
    font_path = Path(windows_root) / "Fonts/segoeui.ttf"
    if not font_path.is_file():
        raise RuntimeError(f"Headless Fluent render font is missing: {font_path}")
    if QFontDatabase.addApplicationFont(str(font_path)) < 0:
        raise RuntimeError(
            f"Qt could not register the headless render font: {font_path}"
        )


def _mount_real_card(theme: Theme) -> _MountedCard:
    """Project the captured SDXL workflow and select its VAE options card."""

    setTheme(theme)
    _register_headless_fluent_font()
    _drain_qt_events(5)
    workflow, definitions = _workflow_from_fixture(read_json(_FIXTURE_PATH))
    host = create_hidden_host(show_window=True)
    panel = _build_editor_panel(
        host=host,
        workflow_id="advanced-input-render-proof",
        definitions=definitions,
    )
    recorder = ProjectionTraceRecorder()
    trace_shell = _build_trace_shell(
        workflow_id="advanced-input-render-proof",
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    panel._cube_states = workflow.cubes
    panel._stack_order = list(workflow.stack_order)
    cube_state = workflow.cubes[_CUBE_ALIAS]
    snapshot = panel._build_behavior_snapshot()
    node_payload = cube_state.buffer["nodes"][_NODE_NAME]
    wrapper = panel.build_node_card(
        _NODE_NAME,
        node_payload["inputs"],
        node_payload["class_type"],
        snapshot.field_specs_by_alias[_CUBE_ALIAS][_NODE_NAME],
        cube_state,
        snapshot.resolved_nodes_by_alias[_CUBE_ALIAS][_NODE_NAME],
        snapshot.card_decisions_by_alias[_CUBE_ALIAS][_NODE_NAME],
        alias=_CUBE_ALIAS,
        parent=panel,
    )
    if not isinstance(wrapper, QWidget):
        host.close()
        raise RuntimeError("Captured SDXL fixture did not build the expected VAE card.")
    panel.card_wrappers[(_CUBE_ALIAS, _NODE_NAME)] = wrapper
    wrapper.show()
    _drain_qt_events(20)
    _verify_real_advanced_surface(panel)
    return _MountedCard(host=host, panel=cast(QWidget, panel), wrapper=wrapper)


def _verify_real_advanced_surface(panel: object) -> None:
    """Fail if the real cube no longer supplies the expected advanced fields."""

    advanced_registry = getattr(panel, "advanced_field_keys", set())
    actual_fields = {
        identity[2]
        for identity in advanced_registry
        if isinstance(identity, tuple)
        and len(identity) >= 3
        and identity[:2] == (_CUBE_ALIAS, _NODE_NAME)
    }
    if actual_fields != _ADVANCED_FIELDS:
        raise RuntimeError(
            f"Expected real VAE advanced fields {_ADVANCED_FIELDS!r}, got {actual_fields!r}."
        )
    grouped_fields = {
        identity[2]
        for identity in getattr(panel, "col_widgets", {})
        if isinstance(identity, tuple)
        and len(identity) >= 3
        and identity[:2] == (_CUBE_ALIAS, _NODE_NAME)
    }
    if not (_ADVANCED_FIELDS & grouped_fields):
        raise RuntimeError(
            "Real VAE advanced fields did not project through grouped rows."
        )


def _apply_state(mounted: _MountedCard, state: str) -> None:
    """Drive the real card through one requested production interaction state."""

    button = mounted.wrapper.findChild(NodeCardActionMenuButton)
    if button is None:
        raise RuntimeError("Projected VAE card has no node action gear.")
    advanced_binding = getattr(mounted.wrapper, "_advanced_input_binding", None)
    toggle_advanced = getattr(advanced_binding, "toggle", None)
    if not callable(toggle_advanced):
        raise RuntimeError("Projected VAE card has no advanced visibility binding.")
    if state in {"shown", "all_advanced"}:
        toggle_advanced()
    if state in {"all_advanced", "all_advanced_hidden"}:
        controller = getattr(mounted.panel, "_field_sync_controller", None)
        apply_hidden = getattr(controller, "apply_hidden_field_keys", None)
        if not callable(apply_hidden):
            raise RuntimeError("Projected editor has no field visibility controller.")
        apply_hidden({(_CUBE_ALIAS, _NODE_NAME, _NORMAL_FIELD)})
    if state == "collapsed":
        content_body = getattr(mounted.wrapper, "_advanced_input_binding")._content_body
        controller = getattr(content_body, "_accordion_motion_controller", None)
        if not isinstance(controller, AccordionMotionController):
            raise RuntimeError("Projected card has no accordion motion controller.")
        controller.toggle()
    _drain_qt_events(20)
    if state == "collapsed":
        body_state = getattr(content_body, "_card_body_layout_state", None)
        if not isinstance(body_state, CardBodyLayoutState) or not body_state.collapsed:
            raise RuntimeError("Projected card did not settle collapsed.")


def _save_widget(widget: QWidget, output_path: Path, *, theme: Theme) -> None:
    """Capture one settled production widget without displaying a desktop window."""

    widget.setFixedWidth(_RENDER_CARD_WIDTH)
    layout = widget.layout()
    if layout is not None:
        layout.activate()
    widget.resize(_RENDER_CARD_WIDTH, widget.sizeHint().height())
    widget.updateGeometry()
    widget.repaint()
    _drain_qt_events(10)
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise RuntimeError(
            f"Could not capture node card geometry for {output_path.name}."
        )
    image.fill(QColor("#202020") if theme is Theme.DARK else QColor("#FFFFFF"))
    painter = QPainter(image)
    widget.render(painter, QPoint())
    painter.end()
    if not image.save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not save node card render to {output_path}.")


def _save_card_with_action_menu(
    mounted: _MountedCard,
    output_path: Path,
    *,
    theme: Theme,
) -> None:
    """Capture a real card with its production gear menu visibly composed."""

    wrapper = mounted.wrapper
    button = wrapper.findChild(NodeCardActionMenuButton)
    if button is None:
        raise RuntimeError("Projected VAE card has no node action gear.")
    title_row = button.parentWidget()
    binding = getattr(title_row, "_node_card_action_menu_binding", None)
    current_menu_model = getattr(binding, "current_menu_model", None)
    if not callable(current_menu_model):
        raise RuntimeError("Projected VAE gear has no action-menu binding.")
    model = current_menu_model()
    if model is None:
        raise RuntimeError("Projected VAE gear unexpectedly produced an empty menu.")
    menu = QFluentMenuRenderer(parent=button).render(model)
    wrapper.setFixedWidth(_RENDER_CARD_WIDTH)
    wrapper_layout = wrapper.layout()
    if wrapper_layout is not None:
        wrapper_layout.activate()
    wrapper.resize(_RENDER_CARD_WIDTH, wrapper.sizeHint().height())
    menu.ensurePolished()
    menu.adjustSize()
    _drain_qt_events(10)
    menu_size = menu.sizeHint().expandedTo(menu.size())
    menu.resize(menu_size)
    menu_gap = 6
    button_origin = button.mapTo(wrapper, QPoint())
    menu_x = min(
        max(0, button_origin.x() + button.width() - menu.width()),
        max(0, wrapper.width() - menu.width()),
    )
    image = QImage(
        wrapper.width(),
        wrapper.height() + menu_gap + menu.height(),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QColor("#202020") if theme is Theme.DARK else QColor("#FFFFFF"))
    painter = QPainter(image)
    wrapper.render(painter, QPoint())
    menu.render(painter, QPoint(menu_x, wrapper.height() + menu_gap))
    painter.end()
    menu.close()
    if not image.save(str(output_path), "PNG"):
        raise RuntimeError(f"Could not save node action menu render to {output_path}.")


def _parse_args() -> argparse.Namespace:
    """Parse the optional non-committed render output directory."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/advanced-input-renders"),
    )
    return parser.parse_args()


def main() -> int:
    """Render every proof scenario and report its absolute PNG path."""

    args = _parse_args()
    for path in render_advanced_input_cards(args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["render_advanced_input_cards"]
