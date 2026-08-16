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

"""Verify semantic cache-producer fingerprint behavior."""

from pathlib import Path

import pytest

from substitute.infrastructure.cache_lifecycle import (
    SemanticSourceFingerprintService,
)


def test_python_format_comments_and_docstrings_do_not_change_fingerprint(
    tmp_path: Path,
) -> None:
    """Avoid invalidating cache data for non-semantic producer edits."""

    source = tmp_path / "producer.py"
    source.write_text(
        '"""First docs."""\n# comment\ndef project(value: int) -> int:\n'
        '    """Function docs."""\n    return value + 1\n',
        encoding="utf-8",
    )
    service = SemanticSourceFingerprintService()
    baseline = service.fingerprint(source_root=tmp_path, python_sources=(source,))
    source.write_text(
        '"""Changed docs."""\n\n# another comment\ndef project( value: int )->int:\n'
        '    """Changed function docs."""\n    return (value + 1)\n',
        encoding="utf-8",
    )

    assert (
        service.fingerprint(
            source_root=tmp_path,
            python_sources=(source,),
        )
        == baseline
    )


def test_python_semantic_change_updates_fingerprint(tmp_path: Path) -> None:
    """Invalidate a derived cache when its declared producer semantics change."""

    source = tmp_path / "producer.py"
    source.write_text(
        "def project(value: int) -> int:\n    return value + 1\n", encoding="utf-8"
    )
    service = SemanticSourceFingerprintService()
    baseline = service.fingerprint(source_root=tmp_path, python_sources=(source,))
    source.write_text(
        "def project(value: int) -> int:\n    return value + 2\n", encoding="utf-8"
    )

    assert (
        service.fingerprint(
            source_root=tmp_path,
            python_sources=(source,),
        )
        != baseline
    )


def test_asset_changes_remain_byte_sensitive(tmp_path: Path) -> None:
    """Invalidate rendered output when one declared visual asset changes."""

    asset = tmp_path / "theme.qss"
    asset.write_text("color: red;", encoding="utf-8")
    service = SemanticSourceFingerprintService()
    baseline = service.fingerprint(source_root=tmp_path, asset_sources=(asset,))
    asset.write_text("color: blue;", encoding="utf-8")

    assert (
        service.fingerprint(
            source_root=tmp_path,
            asset_sources=(asset,),
        )
        != baseline
    )


def test_source_outside_root_is_rejected(tmp_path: Path) -> None:
    """Keep producer declarations inside the trusted application source root."""

    outside = tmp_path.parent / "outside-cache-producer.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="outside allowed root"):
            SemanticSourceFingerprintService().fingerprint(
                source_root=tmp_path,
                python_sources=(outside,),
            )
    finally:
        outside.unlink(missing_ok=True)
