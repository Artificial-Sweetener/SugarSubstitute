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

"""Verify completeness and forward-migration persistence governance."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools.persistence_governance.validation import validate_persistence_governance


def test_catalog_accepts_reviewed_owner_with_complete_migration(tmp_path: Path) -> None:
    """A reviewed v1-to-v2 format should satisfy every governance invariant."""

    owner = _write_owner(tmp_path)
    _write_guidance(tmp_path)
    _write_catalog(tmp_path, owner=owner, migrations='["1->2"]')

    assert validate_persistence_governance(tmp_path) == []


def test_catalog_rejects_missing_historical_migration(tmp_path: Path) -> None:
    """Accepted history must have a contiguous path to the current reader."""

    owner = _write_owner(tmp_path)
    _write_guidance(tmp_path)
    _write_catalog(tmp_path, owner=owner, migrations="[]")

    rules = {item.rule for item in validate_persistence_governance(tmp_path)}

    assert "PERSIST015" in rules


def test_discovery_rejects_uncataloged_schema_owner(tmp_path: Path) -> None:
    """A new literal schema constant must not bypass catalog review."""

    owner = _write_owner(tmp_path)
    extra = tmp_path / "launcher" / "extra.py"
    extra.parent.mkdir(parents=True)
    extra.write_text("EXTRA_SCHEMA_VERSION = 1\n", encoding="utf-8")
    _write_guidance(tmp_path)
    _write_catalog(tmp_path, owner=owner, migrations='["1->2"]')

    rules = {item.rule for item in validate_persistence_governance(tmp_path)}

    assert "PERSIST016" in rules


def _write_owner(root: Path) -> Path:
    """Create one representative versioned persistence owner."""

    owner = root / "substitute" / "session.py"
    owner.parent.mkdir(parents=True)
    owner.write_text('SESSION_SCHEMA_VERSION = "2"\n', encoding="utf-8")
    return owner


def _write_guidance(root: Path) -> None:
    """Create the contributor policy fragments required by the gate."""

    (root / "AGENTS.md").write_text(
        "## Persistence Schema Governance\n"
        "Register every persisted format.\n"
        "For incompatible changes, advance the schema version.\n",
        encoding="utf-8",
    )


def _write_catalog(root: Path, *, owner: Path, migrations: str) -> None:
    """Write one catalog whose aggregate fingerprint matches the owner."""

    relative = owner.relative_to(root).as_posix()
    reviewed = hashlib.sha256(
        relative.encode("utf-8") + b"\0" + owner.read_bytes() + b"\0"
    ).hexdigest()
    catalog = root / "governance" / "persistence" / "catalog.toml"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        f'''schema_version = 1
reviewed_sources_sha256 = "{reviewed}"

[[formats]]
id = "session"
owner = "{relative}"
constant = "SESSION_SCHEMA_VERSION"
current_version = "2"
accepted_versions = ["1", "2"]
classification = "authoritative_state"
compatibility = "migrate"
migrations = {migrations}
''',
        encoding="utf-8",
    )
