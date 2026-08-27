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

"""Verify immutable Comfy source acquisition and offline workspace reuse."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import NoReturn

import pytest

from tools.ci.comfy_source_cache import (
    prepare_comfy_source_cache,
    require_comfy_source_repository,
)
from tools.ci.comfy_source_checkout import checkout_tag, prepare_checkout
from tools.ci.comfy_support_matrix import ComfySupportMatrixEntry


def test_exact_source_cache_reuses_verified_objects_without_upstream(
    tmp_path: Path,
) -> None:
    """A warm cache must materialize and update a checkout entirely offline."""

    upstream, contracts = _create_upstream(tmp_path)
    cache_path = tmp_path / "cache"

    first_result = prepare_comfy_source_cache(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )
    source_repository = require_comfy_source_repository(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )
    upstream.rename(tmp_path / "upstream-offline.git")
    second_result = prepare_comfy_source_cache(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )
    workspace = tmp_path / "workspace"

    prepare_checkout(
        workspace,
        contracts[0].comfyui_tag,
        source_repository=source_repository,
        contracts=contracts,
    )
    checkout_tag(workspace, contracts[1].comfyui_tag, contracts=contracts)

    assert first_result.cache_hit is False
    assert second_result.cache_hit is True
    assert _git_output(workspace, "rev-parse", "HEAD") == contracts[1].commit_sha
    assert (workspace / "version.txt").read_text(encoding="utf-8") == "target"


def test_source_cache_rebuilds_a_misaligned_tag(tmp_path: Path) -> None:
    """A moved cached ref must be rejected and reconstructed from exact pins."""

    upstream, contracts = _create_upstream(tmp_path)
    cache_path = tmp_path / "cache"
    prepare_comfy_source_cache(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )
    source_repository = require_comfy_source_repository(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )
    _run_git(
        source_repository,
        "update-ref",
        f"refs/tags/{contracts[0].comfyui_tag}",
        contracts[1].commit_sha,
    )

    result = prepare_comfy_source_cache(
        cache_path=cache_path,
        repository=str(upstream),
        contracts=contracts,
    )

    assert result.cache_hit is False
    assert (
        _git_output(
            require_comfy_source_repository(
                cache_path=cache_path,
                repository=str(upstream),
                contracts=contracts,
            ),
            "rev-parse",
            f"refs/tags/{contracts[0].comfyui_tag}^{{commit}}",
        )
        == contracts[0].commit_sha
    )


def test_source_cache_rejects_upstream_content_that_disagrees_with_pin(
    tmp_path: Path,
) -> None:
    """An upstream tag move must fail closed before a cache becomes reusable."""

    upstream, contracts = _create_upstream(tmp_path)
    incorrect_contracts = (
        ComfySupportMatrixEntry(
            comfyui_tag=contracts[0].comfyui_tag,
            commit_sha=contracts[1].commit_sha,
            manager_version=contracts[0].manager_version,
            supports_pygit2=contracts[0].supports_pygit2,
        ),
        contracts[1],
    )

    with pytest.raises(RuntimeError, match="does not match the reviewed commit"):
        prepare_comfy_source_cache(
            cache_path=tmp_path / "cache",
            repository=str(upstream),
            contracts=incorrect_contracts,
        )

    assert not (tmp_path / "cache").exists()


def test_source_cache_bounds_external_git_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stalled cold acquisition must fail early instead of consuming the job."""

    contract = ComfySupportMatrixEntry("v1.0.0", "a" * 40, "1.0", False)

    def time_out_git(*_args: object, **_kwargs: object) -> NoReturn:
        """Model a transport that never completes within the owner bound."""

        raise subprocess.TimeoutExpired(cmd=["git"], timeout=120)

    monkeypatch.setattr("tools.ci.comfy_source_cache.subprocess.run", time_out_git)

    with pytest.raises(RuntimeError, match="120-second failure bound"):
        prepare_comfy_source_cache(
            cache_path=tmp_path / "cache",
            repository="https://example.invalid/upstream.git",
            contracts=(contract,),
        )


def _create_upstream(
    tmp_path: Path,
) -> tuple[Path, tuple[ComfySupportMatrixEntry, ...]]:
    """Create two immutable local tags and return their exact contracts."""

    working = tmp_path / "working"
    upstream = tmp_path / "upstream.git"
    working.mkdir()
    _run_git(working, "init")
    _write_version(working, "source")
    _commit(working, "source")
    _run_git(working, "tag", "v1.0.0")
    source_commit = _git_output(working, "rev-parse", "HEAD")
    _write_version(working, "target")
    _commit(working, "target")
    _run_git(working, "tag", "v2.0.0")
    target_commit = _git_output(working, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "clone", "--bare", str(working), str(upstream)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return upstream, (
        ComfySupportMatrixEntry("v1.0.0", source_commit, "1.0", False),
        ComfySupportMatrixEntry("v2.0.0", target_commit, "2.0", True),
    )


def _write_version(repository: Path, version: str) -> None:
    """Write one observable source snapshot."""

    (repository / "version.txt").write_text(version, encoding="utf-8")


def _commit(repository: Path, message: str) -> None:
    """Commit the current fixture snapshot with isolated identity."""

    _run_git(repository, "add", "version.txt")
    _run_git(
        repository,
        "-c",
        "user.name=SugarSubstitute Tests",
        "-c",
        "user.email=tests@example.invalid",
        "commit",
        "--message",
        message,
    )


def _run_git(repository: Path, *arguments: str) -> None:
    """Run one bounded fixture Git command."""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _git_output(repository: Path, *arguments: str) -> str:
    """Return normalized fixture Git output."""

    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result.stdout.strip()
