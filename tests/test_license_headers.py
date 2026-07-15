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

"""Verify automatic GPL license-header maintenance."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from tools.license_headers import (
    PROJECT_TAGLINE,
    UnsupportedLicenseHeaderError,
    copyright_year_range,
    current_utc_year,
    inspect_headers,
    rewrite_source,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_copyright_range_uses_immutable_start_and_automatic_end_year() -> None:
    """The displayed range should advance without annual configuration edits."""

    assert copyright_year_range(2026) == "2026"
    assert copyright_year_range(2027) == "2026-2027"
    assert copyright_year_range(2038) == "2026-2038"
    with pytest.raises(ValueError, match="predates"):
        copyright_year_range(2025)


def test_python_header_preserves_shebang_and_encoding_declaration() -> None:
    """Python interpreter directives must remain before the inserted header."""

    source = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\nprint('ok')\n"

    updated = rewrite_source(source, comment_prefix="#", current_year=2028)

    assert updated.startswith(
        "#!/usr/bin/env python3\n"
        "# -*- coding: utf-8 -*-\n"
        f"#    {PROJECT_TAGLINE}\n"
        "#    Copyright (C) 2026-2028  Artificial Sweetener and contributors\n"
    )
    assert updated.endswith("\n\nprint('ok')\n")


def test_javascript_header_uses_javascript_comments() -> None:
    """JavaScript release tooling should receive the same notice safely."""

    updated = rewrite_source(
        "export const version = '0.9.0';\n",
        comment_prefix="//",
        current_year=2026,
    )

    assert updated.startswith(
        f"//    {PROJECT_TAGLINE}\n"
        "//    Copyright (C) 2026  Artificial Sweetener and contributors\n"
    )
    assert updated.endswith("\n\nexport const version = '0.9.0';\n")


def test_rewrite_updates_year_range_and_is_idempotent() -> None:
    """Rollover should replace only the canonical header and then stabilize."""

    original = rewrite_source('"""Module."""\n', comment_prefix="#", current_year=2026)

    updated = rewrite_source(original, comment_prefix="#", current_year=2029)

    assert "Copyright (C) 2026-2029" in updated
    assert "Copyright (C) 2026  " not in updated
    assert rewrite_source(updated, comment_prefix="#", current_year=2029) == updated


def test_rewrite_refuses_unknown_gpl_header() -> None:
    """Automatic repair must not overwrite a header it does not own."""

    source = "# GNU General Public License, custom notice\nprint('safe')\n"

    with pytest.raises(UnsupportedLicenseHeaderError, match="unrecognized"):
        rewrite_source(source, comment_prefix="#", current_year=2026)


def test_rewrite_allows_gpl_text_inside_source_body() -> None:
    """Embedded license copy should not be mistaken for a file header."""

    source = (
        '"""Expose license copy."""\n\nLICENSE_TEXT = "GNU General Public License"\n'
    )

    updated = rewrite_source(source, comment_prefix="#", current_year=2026)

    assert updated.startswith(f"#    {PROJECT_TAGLINE}\n")
    assert updated.endswith(source)


def test_write_is_transactional_when_a_header_conflicts(tmp_path: Path) -> None:
    """One unknown header should prevent repairs to every governed file."""

    valid_path = tmp_path / "valid.py"
    conflict_path = tmp_path / "conflict.py"
    valid_source = "print('unchanged')\n"
    valid_path.write_text(valid_source, encoding="utf-8")
    conflict_path.write_text(
        "# GNU General Public License, custom notice\nprint('safe')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    updates = inspect_headers(tmp_path, current_year=2026, write=True)

    assert any("unrecognized" in update.reason for update in updates)
    assert valid_path.read_text(encoding="utf-8") == valid_source


def test_repository_headers_are_current() -> None:
    """Every tracked first-party source file should satisfy the live policy."""

    assert (
        inspect_headers(
            PROJECT_ROOT,
            current_year=current_utc_year(),
            write=False,
        )
        == ()
    )
