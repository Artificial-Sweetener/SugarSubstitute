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

"""Own exact, portable Comfy source inputs for compatibility qualification."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Final

from tools.ci.comfy_support_matrix import (
    COMFY_RELEASE_CONTRACTS,
    ComfySupportMatrixEntry,
)


COMFYUI_REPOSITORY: Final[str] = "https://github.com/Comfy-Org/ComfyUI.git"
_CACHE_SCHEMA_VERSION: Final[int] = 1
_MANIFEST_NAME: Final[str] = "manifest.json"
_REPOSITORY_NAME: Final[str] = "repository.git"
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_GIT_TIMEOUT_SECONDS: Final[float] = 120.0


@dataclass(frozen=True, slots=True)
class PreparedComfySourceCache:
    """Report whether exact source objects were reused or reconstructed."""

    cache_path: Path
    repository_path: Path
    cache_hit: bool


def prepare_comfy_source_cache(
    *,
    cache_path: Path,
    repository: str = COMFYUI_REPOSITORY,
    contracts: Sequence[ComfySupportMatrixEntry] = COMFY_RELEASE_CONTRACTS,
) -> PreparedComfySourceCache:
    """Reuse a valid cache or acquire every reviewed tag before qualification."""

    resolved_cache = cache_path.resolve()
    _validate_destination(resolved_cache)
    expected_manifest = _expected_manifest(repository, contracts)
    if _cache_error(resolved_cache, expected_manifest, contracts) is None:
        return PreparedComfySourceCache(
            cache_path=resolved_cache,
            repository_path=resolved_cache / _REPOSITORY_NAME,
            cache_hit=True,
        )

    resolved_cache.parent.mkdir(parents=True, exist_ok=True)
    staging_path = Path(
        tempfile.mkdtemp(
            prefix=f".{resolved_cache.name}.preparing-",
            dir=resolved_cache.parent,
        )
    )
    try:
        _acquire_source_repository(
            staging_path / _REPOSITORY_NAME,
            repository=repository,
            contracts=contracts,
        )
        (staging_path / _MANIFEST_NAME).write_text(
            json.dumps(expected_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        error = _cache_error(staging_path, expected_manifest, contracts)
        if error is not None:
            raise RuntimeError(f"Prepared Comfy source cache is invalid: {error}")
        _replace_cache(resolved_cache, staging_path)
    finally:
        if staging_path.exists():
            _remove_exact_path(staging_path)

    return PreparedComfySourceCache(
        cache_path=resolved_cache,
        repository_path=resolved_cache / _REPOSITORY_NAME,
        cache_hit=False,
    )


def require_comfy_source_repository(
    *,
    cache_path: Path,
    repository: str = COMFYUI_REPOSITORY,
    contracts: Sequence[ComfySupportMatrixEntry] = COMFY_RELEASE_CONTRACTS,
) -> Path:
    """Return a verified local source repository or reject incomplete input."""

    resolved_cache = cache_path.resolve()
    error = _cache_error(
        resolved_cache,
        _expected_manifest(repository, contracts),
        contracts,
    )
    if error is not None:
        raise RuntimeError(f"Comfy source cache is unavailable or invalid: {error}")
    return resolved_cache / _REPOSITORY_NAME


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare one cache and emit auditable reuse evidence."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-path", type=Path, required=True)
    arguments = parser.parse_args(argv)
    result = prepare_comfy_source_cache(cache_path=arguments.cache_path)
    print(
        json.dumps(
            {
                "cache_hit": result.cache_hit,
                "cache_path": str(result.cache_path),
                "repository_path": str(result.repository_path),
                "source_pins": {
                    contract.comfyui_tag: contract.commit_sha
                    for contract in COMFY_RELEASE_CONTRACTS
                },
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def _expected_manifest(
    repository: str,
    contracts: Sequence[ComfySupportMatrixEntry],
) -> dict[str, object]:
    """Return the exact semantic identity allowed in reusable storage."""

    _validate_contracts(contracts)
    return {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "repository": repository,
        "source_pins": [
            {"tag": contract.comfyui_tag, "commit_sha": contract.commit_sha}
            for contract in contracts
        ],
    }


def _validate_contracts(contracts: Sequence[ComfySupportMatrixEntry]) -> None:
    """Reject incomplete or ambiguous immutable source identities."""

    if not contracts:
        raise ValueError("At least one Comfy source contract is required.")
    tags = [contract.comfyui_tag for contract in contracts]
    if len(tags) != len(set(tags)):
        raise ValueError("Comfy source contracts contain duplicate tags.")
    for contract in contracts:
        if not _COMMIT_SHA.fullmatch(contract.commit_sha):
            raise ValueError(
                f"Comfy source pin for {contract.comfyui_tag!r} is not a full SHA."
            )


def _acquire_source_repository(
    destination: Path,
    *,
    repository: str,
    contracts: Sequence[ComfySupportMatrixEntry],
) -> None:
    """Fetch all reviewed shallow snapshots in one fail-fast remote transaction."""

    _run_git(destination.parent, "init", "--bare", str(destination))
    refspecs = [
        f"+refs/tags/{contract.comfyui_tag}:refs/tags/{contract.comfyui_tag}"
        for contract in contracts
    ]
    _run_git(
        destination,
        "fetch",
        "--no-tags",
        "--depth",
        "1",
        repository,
        *refspecs,
    )
    for contract in contracts:
        actual_commit = _git_output(
            destination,
            "rev-parse",
            f"refs/tags/{contract.comfyui_tag}^{{commit}}",
        )
        if actual_commit != contract.commit_sha:
            raise RuntimeError(
                f"Upstream tag {contract.comfyui_tag!r} at {actual_commit!r} "
                f"does not match the reviewed commit {contract.commit_sha!r}."
            )


def _cache_error(
    cache_path: Path,
    expected_manifest: dict[str, object],
    contracts: Sequence[ComfySupportMatrixEntry],
) -> str | None:
    """Return the first integrity error without mutating disposable storage."""

    manifest_path = cache_path / _MANIFEST_NAME
    source_repository = cache_path / _REPOSITORY_NAME
    if not cache_path.is_dir():
        return "cache directory is absent"
    if not manifest_path.is_file():
        return "identity manifest is absent"
    try:
        actual_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return f"identity manifest is unreadable: {error}"
    if actual_manifest != expected_manifest:
        return "identity manifest does not match the reviewed source contracts"
    if not source_repository.is_dir():
        return "bare source repository is absent"
    if _git_output(source_repository, "rev-parse", "--is-bare-repository") != "true":
        return "source repository is not bare"
    for contract in contracts:
        actual_commit = _git_output(
            source_repository,
            "rev-parse",
            f"refs/tags/{contract.comfyui_tag}^{{commit}}",
        )
        if actual_commit != contract.commit_sha:
            return (
                f"tag {contract.comfyui_tag} resolves to {actual_commit!r}, "
                f"expected {contract.commit_sha!r}"
            )
    result = _git_result(
        source_repository,
        "fsck",
        "--connectivity-only",
        "--no-dangling",
    )
    if result.returncode != 0:
        return f"Git object connectivity failed: {_command_error(result)}"
    return None


def _replace_cache(destination: Path, staging_path: Path) -> None:
    """Promote a fully verified cache while retaining rollback on rename failure."""

    backup_path = destination.with_name(f".{destination.name}.replaced")
    if backup_path.exists():
        _remove_exact_path(backup_path)
    if destination.exists():
        destination.rename(backup_path)
    try:
        staging_path.rename(destination)
    except OSError:
        if backup_path.exists() and not destination.exists():
            backup_path.rename(destination)
        raise
    if backup_path.exists():
        _remove_exact_path(backup_path)


def _remove_exact_path(path: Path) -> None:
    """Remove one validated cache-owned path without broad path expansion."""

    _validate_destination(path.resolve())
    if path.is_dir():
        shutil.rmtree(path, onexc=_clear_readonly)
    else:
        path.chmod(stat.S_IWRITE)
        path.unlink()


def _clear_readonly(
    operation: Callable[[str], object],
    path: str,
    error: BaseException,
) -> None:
    """Clear Git object read-only bits only when Windows denies cache cleanup."""

    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    operation(path)


def _validate_destination(path: Path) -> None:
    """Reject filesystem roots and empty names as disposable cache targets."""

    if path.parent == path or not path.name or path == Path.cwd().resolve():
        raise ValueError(f"Unsafe Comfy source-cache destination: {path}")


def _run_git(repository: Path, *arguments: str) -> None:
    """Run one bounded Git operation and preserve useful failure diagnostics."""

    result = _git_result(repository, *arguments)
    if result.returncode != 0:
        raise RuntimeError(
            f"Git source-cache operation failed: {_command_error(result)}"
        )


def _git_output(repository: Path, *arguments: str) -> str:
    """Return normalized output from a non-mutating Git query."""

    result = _git_result(repository, *arguments)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_result(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Execute Git without an interactive console or inherited noisy output."""

    command = ["git", *arguments]
    try:
        return subprocess.run(
            command,
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "Git source-cache operation exceeded its 120-second failure bound: "
            f"{command!r}."
        ) from error


def _command_error(result: subprocess.CompletedProcess[str]) -> str:
    """Return bounded stderr/stdout evidence for a failed Git operation."""

    return (result.stderr.strip() or result.stdout.strip() or "no Git output")[-4000:]


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMFYUI_REPOSITORY",
    "PreparedComfySourceCache",
    "prepare_comfy_source_cache",
    "require_comfy_source_repository",
]
