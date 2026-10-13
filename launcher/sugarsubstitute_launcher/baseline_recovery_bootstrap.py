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

"""Release mapped Windows images before recovering a partially replaced baseline."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.baseline_recovery_request import (
    BaselineRecoveryRequest,
)
from sugarsubstitute_shared.application_readiness import (
    without_application_readiness_environment,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    without_crash_supervision_environment,
)
from sugarsubstitute_shared.launcher_update.baseline_transaction import (
    LauncherBaselineTransaction,
)
from sugarsubstitute_shared.launcher_update.targets import WINDOWS_X64_BUNDLE
from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
    capture_process_identity,
    wait_for_process_exit,
)
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
    standard_child_process_dll_search_path,
)
from sugarsubstitute_shared.windows_independent_process import (
    start_independent_windows_process,
)

_RECOVERY_ARGUMENT = "--recover-launcher-baseline"
_LOGGER = logging.getLogger(__name__)


def run_baseline_recovery_bootstrap(arguments: Sequence[str]) -> int | None:
    """Handle owned recovery before importing a replaceable runtime or application."""
    if sys.platform != "win32" or not bool(getattr(sys, "frozen", False)):
        return None
    image = Path(sys.executable).resolve()
    if arguments and arguments[0] == _RECOVERY_ARGUMENT:
        if len(arguments) != 2:
            raise ValueError("usage: --recover-launcher-baseline REQUEST_PATH")
        path = Path(arguments[1]).resolve()
        request = BaselineRecoveryRequest.load(path)
        if image == request.install_root / WINDOWS_X64_BUNDLE.executable_relative_path:
            return _handoff(
                request.install_root, request.arguments, relaunch=request.relaunch
            )
        if image != path.parent / "Recovery.exe":
            raise ValueError("Baseline recovery helper is outside its request owner.")
        for identity in request.wait_identities:
            wait_for_process_exit(identity, timeout_seconds=120)
        LauncherBaselineTransaction().recover(
            install_root=request.install_root, target=WINDOWS_X64_BUNDLE
        )
        write_json_atomic(
            path.with_name("completed.json"),
            {
                **read_json_object(path),
                "completed_identities": [
                    {"pid": identity.pid, "created_at": identity.created_at}
                    for identity in _mapped_image_identities(image)
                ],
            },
        )
        path.unlink()
        if request.relaunch:
            _start_hidden(
                [
                    str(
                        request.install_root
                        / WINDOWS_X64_BUNDLE.executable_relative_path
                    ),
                    *request.arguments,
                ],
                request.install_root,
            )
        return 0
    root = _installation_root(arguments, image)
    if image != root / WINDOWS_X64_BUNDLE.executable_relative_path:
        return None
    _retire_inactive_helper_images(root)
    if not (root / "launcher" / "updates" / "transaction.json").exists():
        return None
    return _handoff(root, arguments, relaunch=True)


def _retire_inactive_helper_images(root: Path) -> None:
    """Retain handoff evidence while removing owned, inactive copied executables.

    A live publishing process protects the copy before native creation. Once it
    exits, Windows image sharing protects both helper and bootloader mappings;
    an image still in use cannot be unlinked. Unknown directories stay intact.
    """
    namespace = root / "launcher" / "updates" / "recovery"
    try:
        directories = tuple(namespace.iterdir())
    except FileNotFoundError:
        return
    except OSError:
        _LOGGER.warning("Recovery image cleanup unavailable", exc_info=True)
        return
    for directory in directories:
        if len(directory.name) != 32 or any(
            character not in "0123456789abcdef" for character in directory.name
        ):
            continue
        try:
            if not directory.is_dir() or directory.resolve() != directory:
                continue
            path = directory / "request.json"
            if not path.is_file():
                path = directory / "completed.json"
            request = BaselineRecoveryRequest.load(path)
            if request.install_root != root or not request.wait_identities:
                continue
            for identity in request.wait_identities:
                wait_for_process_exit(identity, timeout_seconds=0)
            helper = directory / "Recovery.exe"
            if helper.is_symlink():
                continue
            helper.unlink(missing_ok=True)
        except (FileNotFoundError, ProcessIdentityError):
            continue
        except (OSError, ValueError):
            _LOGGER.warning(
                "Recovery image cleanup deferred | directory=%s",
                directory,
                exc_info=True,
            )


def _installation_root(arguments: Sequence[str], image: Path) -> Path:
    """Honor an explicit installation root without importing application setup."""
    for index, argument in enumerate(arguments):
        if argument.startswith("--install-root="):
            return Path(argument.split("=", 1)[1]).expanduser().resolve()
        if argument == "--install-root" and index + 1 < len(arguments):
            return Path(arguments[index + 1]).expanduser().resolve()
    return image.parent


def _mapped_image_identities(image: Path) -> tuple[ProcessIdentity, ...]:
    """Wait for both the application and its same-image onefile bootloader parent."""
    identities = [capture_process_identity(os.getpid())]
    parent = psutil.Process(os.getppid())
    if Path(parent.exe()).resolve() == image:
        identities.append(capture_process_identity(parent.pid))
    return tuple(identities)


def _handoff(root: Path, arguments: Sequence[str], *, relaunch: bool) -> int:
    """Start a byte-identical independent helper before releasing the mapped image."""
    image = Path(sys.executable).resolve()
    directory = root / "launcher" / "updates" / "recovery" / uuid4().hex
    directory.mkdir(parents=True)
    helper = directory / "Recovery.exe"
    path = directory / "request.json"
    BaselineRecoveryRequest(
        root, tuple(arguments), _mapped_image_identities(image), relaunch
    ).save(path)
    shutil.copy2(image, helper)
    with image.open("rb") as source, helper.open("rb") as copied:
        if (
            hashlib.file_digest(source, "sha256").digest()
            != hashlib.file_digest(copied, "sha256").digest()
        ):
            raise ValueError("Baseline recovery helper changed during copying.")
    pid = _start_hidden([str(helper), _RECOVERY_ARGUMENT, str(path)], root)
    _LOGGER.info("Scheduled independent baseline recovery | helper_pid=%s", pid)
    return 0


def _start_hidden(command: list[str], root: Path) -> int:
    """Use the existing native independence owner with clean frozen runtime state."""
    environment = without_application_readiness_environment(
        without_crash_supervision_environment(clean_frozen_parent_environment())
    )
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    log_path = root / "launcher" / "logs" / "launcher-recovery.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        log_path.open("a", encoding="utf-8") as output,
        standard_child_process_dll_search_path(),
    ):
        return start_independent_windows_process(
            command, environment=environment, cwd=root, output_fd=output.fileno()
        )
