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

"""Test Cube Library pack and readiness presentation."""

from __future__ import annotations


import pytest
from qfluentwidgets import PushButton  # type: ignore[import-untyped]

from tests.presentation.settings.cube_library.support import (
    application,
    build_page,
    description_label_texts,
    header_button_texts,
    pack,
    pack_button,
    pack_list_button,
    readiness,
    snapshot,
    title_label_texts,
)


def test_cube_library_page_renders_packs_and_selection_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pack rows and direct actions should render without table selection."""

    app = application()
    page = build_page(monkeypatch)
    library_snapshot = snapshot(
        packs=(
            pack(owner="Owner", repo="Editable", default_base_repo=False),
            pack(owner="Base", repo="Default", default_base_repo=True),
        ),
        readiness=readiness(missing_custom_nodes=()),
    )

    page._apply_snapshot(library_snapshot)
    app.processEvents()

    assert page.rendered_pack_refs() == ("Owner/Editable", "Base/Default")
    assert tuple(page._pack_expanders) == ("Owner/Editable", "Base/Default")
    assert not hasattr(page, "pack_table")
    assert page.readiness_container.findChildren(PushButton) == []
    assert "Required custom nodes are installed." in description_label_texts(
        page.readiness_container
    )

    editable_remove = pack_button(page, "Owner/Editable", "Remove")
    default_remove = pack_button(page, "Base/Default", "Remove")

    assert editable_remove.isEnabled() is True
    assert default_remove.isEnabled() is False
    assert "demo.cube" in description_label_texts(
        page._pack_expanders["Owner/Editable"].content_widget()
    )
    assert header_button_texts(page, "Owner/Editable") == []
    page.close()


def test_cube_library_page_renders_missing_readiness_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing readiness should list custom-node names in the page."""

    app = application()
    page = build_page(monkeypatch)

    page._apply_snapshot(
        snapshot(
            packs=(),
            readiness=readiness(missing_custom_nodes=("Impact Pack",)),
        )
    )
    app.processEvents()

    labels = description_label_texts(page.readiness_container)

    assert "Missing custom nodes: 1" in labels
    assert "Impact Pack" in labels
    page.close()


def test_cube_library_page_renders_empty_state_and_add_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty pack state should offer a focused add-pack action."""

    app = application()
    page = build_page(monkeypatch)

    page._apply_snapshot(
        snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))
    )
    app.processEvents()

    empty_titles = title_label_texts(page.pack_list)
    assert "No Cube Packs tracked" in empty_titles
    assert page.add_pack_expander.is_expanded() is False

    pack_list_button(page, "Add Cube Pack").click()
    app.processEvents()

    assert page.add_pack_expander.is_expanded() is False
    assert page.add_pack_expander.has_content_available() is False
    page.close()


def test_cube_library_page_unavailable_snapshot_clears_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable snapshots should clear pack rows and show unavailable status."""

    app = application()
    page = build_page(monkeypatch)

    page._apply_snapshot(None)
    app.processEvents()

    assert page.rendered_pack_refs() == ()
    assert page.status_row.description_label.text() == (
        "Cube Library unavailable on the active target."
    )
    assert page.notification_bar.severity() == "error"
    page.close()


def test_cube_library_page_ready_readiness_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready readiness should keep the existing success copy."""

    app = application()
    page = build_page(monkeypatch)

    page._apply_snapshot(
        snapshot(packs=(), readiness=readiness(missing_custom_nodes=()))
    )
    app.processEvents()

    labels = description_label_texts(page.readiness_container)
    assert "Required custom nodes are installed." in labels
    page.close()
