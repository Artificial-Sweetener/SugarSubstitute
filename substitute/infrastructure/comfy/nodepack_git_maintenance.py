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

"""Maintain git-backed Comfy nodepack checkouts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
import json
from pathlib import Path
import zipfile

from substitute.infrastructure.comfy.nodepack_manifest import (
    CoreComfyNodepack,
    NODEPACK_BACKUP_KEEP_COUNT,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    path_is_relative_to,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.nodepack_git_maintenance")


def try_backup_git_nodepack_before_replacement(
    *,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    reason: str,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None = None,
) -> None:
    """Best-effort backup a git nodepack before destructive managed replacement."""

    if not (target_path / ".git").exists():
        return
    try:
        backup_path = backup_git_nodepack_before_replacement(
            target_path=target_path,
            nodepack=nodepack,
            reason=reason,
            env=env,
            repositories=repositories,
        )
    except Exception as exc:
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] WARNING: Could not back up local "
                f"{nodepack.display_name} checkout before replacement: {exc}"
            ),
        )
        return
    _emit_log(
        on_log,
        f"[ComfyNodepacks] Backed up local {nodepack.display_name} checkout to {backup_path}.",
    )


def backup_git_nodepack_before_replacement(
    *,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    reason: str,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None = None,
) -> Path:
    """Archive tracked git checkout state without saving untracked worktree files."""

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    backup_dir = _nodepack_backup_directory(target_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_stem = f"{timestamp}-{reason}"
    backup_path = backup_dir / f"{backup_stem}.zip"
    metadata_path = backup_dir / f"{backup_stem}.json"
    del env
    selected_repositories = repositories or repository_service()
    tracked_files = selected_repositories.tracked_files(target_path)
    with zipfile.ZipFile(
        backup_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        _write_git_metadata_to_backup(
            archive=archive,
            target_path=target_path,
        )
        _write_tracked_worktree_files_to_backup(
            archive=archive,
            target_path=target_path,
            tracked_files=tracked_files,
        )
    metadata = {
        "nodepack": nodepack.display_name,
        "projectName": nodepack.project_name,
        "reason": reason,
        "sourcePath": str(target_path),
        "createdUtc": datetime.now(tz=UTC).isoformat(),
        "untrackedFilesIncluded": False,
        "trackedFileCount": len(tracked_files),
        "gitStatus": selected_repositories.status_excerpt(target_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _prune_nodepack_backups(backup_dir)
    return backup_path


def checkout_pinned_git_tag(
    *,
    target_path: Path,
    nodepack: CoreComfyNodepack,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None = None,
) -> None:
    """Move an existing git-backed nodepack to the pinned required tag."""

    if (
        nodepack.source_url is None
        or nodepack.required_python_distribution_version is None
    ):
        raise RuntimeError(f"{nodepack.display_name} has no pinned git fallback tag.")
    tag = f"v{nodepack.required_python_distribution_version}"
    _emit_log(
        on_log,
        f"[ComfyNodepacks] Checking out {nodepack.display_name} tag {tag}.",
    )
    del env
    selected_repositories = repositories or repository_service()
    try:
        selected_repositories.fetch_tag(
            target_path,
            repository_url=nodepack.source_url,
            tag=tag,
            on_progress=on_log,
        )
        selected_repositories.checkout_revision(target_path, tag)
    except RepositoryOperationError as error:
        raise RuntimeError(
            f"Could not check out {nodepack.display_name} fallback tag {tag}."
        ) from error


def refresh_git_nodepack(
    target_path: Path,
    *,
    on_log: LogCallback | None,
    env: Mapping[str, str] | None,
    repositories: RepositoryService | None = None,
) -> bool:
    """Fast-forward one git-backed nodepack when it is safe to do so."""

    if not (target_path / ".git").exists():
        return False
    del env
    try:
        (repositories or repository_service()).sync_fast_forward(
            target_path,
            on_progress=on_log,
        )
    except RepositoryOperationError:
        _emit_log(
            on_log,
            (
                f"[ComfyNodepacks] Git fast-forward failed for {target_path}; "
                "using managed replacement fallback."
            ),
        )
        return False
    return True


def _nodepack_backup_directory(target_path: Path) -> Path:
    """Return the workspace-local backup directory for one managed nodepack."""

    if target_path.parent.name == "custom_nodes":
        workspace = target_path.parent.parent
    else:
        workspace = target_path.parent
    return (
        workspace
        / "user"
        / "sugarsubstitute"
        / "managed-nodepack-backups"
        / target_path.name
    )


def _write_git_metadata_to_backup(
    *,
    archive: zipfile.ZipFile,
    target_path: Path,
) -> None:
    """Write the checkout's `.git` metadata into the backup archive."""

    git_path = target_path / ".git"
    if git_path.is_file():
        archive.write(git_path, _backup_archive_name(target_path, git_path))
        return
    for file_path in sorted(git_path.rglob("*")):
        if file_path.is_file():
            archive.write(file_path, _backup_archive_name(target_path, file_path))


def _write_tracked_worktree_files_to_backup(
    *,
    archive: zipfile.ZipFile,
    target_path: Path,
    tracked_files: Sequence[Path],
) -> None:
    """Write tracked worktree files while intentionally skipping untracked files."""

    root = target_path.resolve()
    for relative_path in tracked_files:
        file_path = (target_path / relative_path).resolve()
        if not path_is_relative_to(file_path, root) or not file_path.is_file():
            continue
        archive.write(file_path, _backup_archive_name(target_path, file_path))


def _backup_archive_name(target_path: Path, file_path: Path) -> str:
    """Return a stable archive name rooted at the nodepack folder."""

    relative_path = file_path.resolve().relative_to(target_path.resolve())
    return f"{target_path.name}/{relative_path.as_posix()}"


def _prune_nodepack_backups(backup_dir: Path) -> None:
    """Keep only the latest managed replacement backups for one nodepack."""

    backups = sorted(
        backup_dir.glob("*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for stale_backup in backups[NODEPACK_BACKUP_KEEP_COUNT:]:
        stale_backup.unlink(missing_ok=True)
        stale_backup.with_suffix(".json").unlink(missing_ok=True)


def _emit_log(callback: LogCallback | None, message: str) -> None:
    """Emit one git-maintenance line to logs and optional setup output."""

    log_info(_LOGGER, message)
    if callback is not None:
        callback(message)


__all__ = [
    "backup_git_nodepack_before_replacement",
    "checkout_pinned_git_tag",
    "refresh_git_nodepack",
    "try_backup_git_nodepack_before_replacement",
]
