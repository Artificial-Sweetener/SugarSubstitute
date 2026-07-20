#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Keep dynamic UI copy bound and authored input free from ASCII restrictions."""

from __future__ import annotations

from pathlib import Path

from tools.check_localization import (
    find_ascii_input_restrictions,
    find_non_fluent_tooltip_usage,
)
from tools.localization_catalog import (
    find_unbound_dynamic_messages,
    find_unclassified_presentation_assignments,
    find_unclassified_presentation_returns,
    find_unmarked_application_messages,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dynamic_presentation_messages_use_localization_owners() -> None:
    """Translatable f-strings must retain sources for live language changes."""

    assert find_unbound_dynamic_messages(_PROJECT_ROOT) == ()


def test_presentation_inputs_have_no_ascii_only_source_restrictions() -> None:
    """Authored text must not be limited to English letters by UI code."""

    assert find_ascii_input_restrictions(_PROJECT_ROOT) == ()


def test_all_tooltips_use_the_shared_qfluent_owner() -> None:
    """Native and competing tooltip paths must fail source policy."""

    assert find_non_fluent_tooltip_usage(_PROJECT_ROOT) == ()


def test_tooltip_policy_rejects_indirect_native_property_writes(
    tmp_path: Path,
) -> None:
    """Dynamic property access must not evade the QFluent-only invariant."""

    source_root = tmp_path / "substitute"
    source_root.mkdir()
    (source_root / "bad_tooltip.py").write_text(
        "getattr(widget, 'setToolTip')('native')\n"
        "widget.setProperty('toolTip', 'native')\n",
        encoding="utf-8",
    )

    violations = find_non_fluent_tooltip_usage(tmp_path)

    assert tuple(item.reason for item in violations) == (
        "indirect setToolTip access must use the shared QFluent owner",
        "tooltip property writes must use the shared QFluent owner",
    )


def test_visible_application_copy_has_an_explicit_locale_owner() -> None:
    """Static app copy must be marked instead of inferred from widget state."""

    assert find_unmarked_application_messages(_PROJECT_ROOT) == ()
    assert find_unclassified_presentation_assignments(_PROJECT_ROOT) == ()
    assert find_unclassified_presentation_returns(_PROJECT_ROOT) == ()


def test_visible_badge_and_teaching_tip_copy_cannot_bypass_policy(
    tmp_path: Path,
) -> None:
    """Catch raw copy in QFluent factories that do not use widget constructors."""

    source_root = tmp_path / "substitute" / "presentation"
    source_root.mkdir(parents=True)
    (source_root / "qfluent_factories.py").write_text(
        "InfoBadge.info('Raw badge', parent)\n"
        "InfoBadge.error(app_text('Owned badge'), parent)\n"
        "TeachingTip.create(target=parent, title='', content='Raw tip')\n",
        encoding="utf-8",
    )

    violations = find_unmarked_application_messages(tmp_path)

    assert tuple(item.source for item in violations) == ("Raw badge", "Raw tip")


def test_presentation_return_policy_requires_explicit_classification(
    tmp_path: Path,
) -> None:
    """Presentation helpers must mark owned copy and classify opaque content."""

    source_root = tmp_path / "substitute" / "presentation"
    source_root.mkdir(parents=True)
    (source_root / "return_copy.py").write_text(
        "def status_message():\n"
        "    return 'Visible English'\n\n"
        "def opaque_title():\n"
        "    return opaque_text('Authored title')\n\n"
        "def localized_tooltip():\n"
        "    return app_text('Localized tooltip')\n",
        encoding="utf-8",
    )

    violations = find_unclassified_presentation_returns(tmp_path)

    assert tuple(item.source for item in violations) == ("Visible English",)
