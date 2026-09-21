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

"""Discover, validate, and safely copy workflow mask recovery evidence."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.util.path_safety import ensure_within_root

_LOGGER = get_logger("infrastructure.persistence.workflow_mask_recovery_evidence")


@dataclass(frozen=True, slots=True)
class MaskRecoveryCandidate:
    """Describe one verified recovery source without exposing its content."""

    path: Path
    owner: str
    digest: str
    has_authored_pixels: bool
    modified_ns: int


class WorkflowMaskRecoveryEvidence:
    """Own project-contained candidate discovery, validation, and safe copying."""

    def __init__(self, *, projects_dir: Path) -> None:
        """Store the resolved boundary that all evidence must remain beneath."""

        self._projects_dir = projects_dir.resolve()

    def inspect(self, path: Path, *, owner: str = "") -> MaskRecoveryCandidate | None:
        """Return verified image facts for a project-contained candidate."""

        try:
            safe_path = ensure_within_root(
                path,
                root_path=self._projects_dir,
                subject="workflow mask recovery candidate",
            )
            if not safe_path.is_file():
                return None
            with Image.open(safe_path) as image:
                image.load()
                has_authored_pixels = image.getbbox() is not None
            payload = safe_path.read_bytes()
            stat = safe_path.stat()
        except (OSError, ValueError, UnidentifiedImageError):
            return None
        return MaskRecoveryCandidate(
            path=safe_path,
            owner=owner,
            digest=sha256(payload).hexdigest(),
            has_authored_pixels=has_authored_pixels,
            modified_ns=stat.st_mtime_ns,
        )

    def canonical_candidate(
        self,
        owner: str,
        relative_path: Path,
    ) -> MaskRecoveryCandidate | None:
        """Inspect one exact owner-relative canonical mask path."""

        if not owner or Path(owner).name != owner:
            return None
        return self.inspect(
            self._projects_dir / owner / "masks" / relative_path,
            owner=owner,
        )

    def canonical_candidates(
        self,
        relative_path: Path,
    ) -> tuple[MaskRecoveryCandidate, ...]:
        """Return valid exact relative-path matches under legacy project owners."""

        candidates: list[MaskRecoveryCandidate] = []
        if not self._projects_dir.is_dir():
            return ()
        for owner_root in sorted(
            self._projects_dir.iterdir(), key=lambda path: path.name
        ):
            if not owner_root.is_dir():
                continue
            candidate = self.inspect(
                owner_root / "masks" / relative_path,
                owner=owner_root.name,
            )
            if candidate is not None:
                candidates.append(candidate)
        return tuple(candidates)

    def generation_candidates(
        self,
        mask_id: str,
    ) -> tuple[MaskRecoveryCandidate, ...]:
        """Return valid generation revisions for one stable mask identity."""

        candidates: list[MaskRecoveryCandidate] = []
        if not self._projects_dir.is_dir():
            return ()
        for owner_root in sorted(
            self._projects_dir.iterdir(), key=lambda path: path.name
        ):
            revision_root = owner_root / "masks" / ".generation" / mask_id
            if not revision_root.is_dir():
                continue
            for path in sorted(revision_root.rglob("*")):
                candidate = self.inspect(path, owner=owner_root.name)
                if candidate is not None:
                    candidates.append(candidate)
        return tuple(candidates)

    def select_equivalent(
        self,
        candidates: tuple[MaskRecoveryCandidate, ...],
        *,
        workflow_id: str,
        mask_id: str,
        source_kind: str,
    ) -> MaskRecoveryCandidate | None:
        """Choose newest equivalent evidence or retain conflicting candidates."""

        if not candidates:
            return None
        digests = {candidate.digest for candidate in candidates}
        if len(digests) != 1:
            log_warning(
                _LOGGER,
                "Retained conflicting workflow mask recovery candidates",
                workflow_id=workflow_id,
                mask_id=mask_id,
                source_kind=source_kind,
                candidate_count=len(candidates),
                distinct_content_count=len(digests),
            )
            return None
        return max(
            candidates,
            key=lambda candidate: (candidate.modified_ns, candidate.path.name),
        )

    def copy_verified(
        self,
        source: MaskRecoveryCandidate,
        destination: Path,
    ) -> Path | None:
        """Atomically copy evidence without overwriting different known content."""

        temporary: Path | None = None
        try:
            safe_destination = ensure_within_root(
                destination,
                root_path=self._projects_dir,
                subject="workflow mask recovery destination",
            )
            safe_destination.parent.mkdir(parents=True, exist_ok=True)
            existing = self.inspect(safe_destination)
            if existing is not None:
                return safe_destination if existing.digest == source.digest else None
            temporary = safe_destination.with_name(
                f".{safe_destination.name}.{uuid4().hex}.tmp"
            )
            shutil.copyfile(source.path, temporary)
            copied = self.inspect(temporary)
            if copied is None or copied.digest != source.digest:
                temporary.unlink(missing_ok=True)
                return None
            os.replace(temporary, safe_destination)
            return safe_destination
        except (OSError, ValueError) as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            log_warning(
                _LOGGER,
                "Workflow mask recovery copy failed",
                mask_digest=source.digest,
                error=repr(error),
            )
            return None


__all__ = ["MaskRecoveryCandidate", "WorkflowMaskRecoveryEvidence"]
