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

"""Resolve supervised process evidence into one durable crash incident."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import signal

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
)
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.protocol import (
    CleanExitEvidence,
    CrashRunContext,
)
from sugarsubstitute_shared.crash_reporting.run_context import (
    CrashRunRuntimeContext,
    CrashRunRuntimeContextStore,
    STARTUP_OUTPUT_FILENAME,
)


_LOGGER = logging.getLogger(__name__)


def resolve_process_incident(
    *,
    layout: InstallLayout,
    context: CrashRunContext,
    process_id: int,
    return_code: int,
    minidump: Path | None,
    application_version: str | None,
    platform_name: str,
    python_version: str,
    launch_arguments: tuple[str, ...],
    termination: SupervisedTermination,
    exit_evidence: CleanExitEvidence,
) -> CrashIncident:
    """Enrich in-process evidence or synthesize an accurate termination report."""

    store = CrashIncidentStore(context.incident_root)
    retained_dump = _retain_minidump(store, context.run_id, minidump)
    recorded_runtime_context = CrashRunRuntimeContextStore(context.incident_root).load(
        context.run_id
    )
    runtime_context = recorded_runtime_context or CrashRunRuntimeContext(
        process_id=process_id,
        application_version=application_version,
        platform=platform_name,
        python_version=python_version,
        launch_arguments=launch_arguments,
        install_root=str(layout.root),
    )
    fault_log = store.attachment_path(context.run_id, "python-fault.log")
    startup_output = store.attachment_path(context.run_id, STARTUP_OUTPUT_FILENAME)
    diagnostic_attachments = _meaningful_attachments(
        fault_log=fault_log,
        startup_output=startup_output,
        retained_dump=retained_dump,
    )
    metadata = _termination_metadata(
        termination=termination,
        exit_evidence=exit_evidence,
        runtime_context_source=(
            "application"
            if recorded_runtime_context is not None
            else "supervisor_fallback"
        ),
        fault_log=fault_log,
        startup_output=startup_output,
    )
    if runtime_context.process_id != process_id:
        metadata["supervisor_process_id"] = str(process_id)
    existing = next(
        (item for item in store.pending() if item.run_id == context.run_id),
        None,
    )
    if existing is not None:
        return _enrich_existing_incident(
            store=store,
            existing=existing,
            return_code=return_code,
            diagnostic_attachments=diagnostic_attachments,
            runtime_context=runtime_context,
            metadata=metadata,
        )

    kind, boundary, attribution, summary = _synthesized_termination(
        minidump=minidump,
        fault_log=fault_log,
        return_code=return_code,
        termination=termination,
    )
    incident = CrashIncident(
        incident_id=context.run_id,
        run_id=context.run_id,
        occurred_at_utc=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        boundary=boundary,
        attribution=attribution,
        summary=summary,
        process_id=runtime_context.process_id,
        exit_code=return_code,
        application_version=runtime_context.application_version,
        platform=runtime_context.platform,
        python_version=runtime_context.python_version,
        launch_arguments=runtime_context.launch_arguments,
        attachments=diagnostic_attachments,
        metadata=metadata,
    )
    store.record(incident)
    return incident


def newest_run_minidump(database: Path, started_at_ns: int) -> Path | None:
    """Return the newest Crashpad dump created during this supervised run."""

    if not database.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in database.rglob("*.dmp"):
        try:
            modified_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        if modified_ns >= started_at_ns:
            candidates.append((modified_ns, path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _retain_minidump(
    store: CrashIncidentStore,
    run_id: str,
    minidump: Path | None,
) -> Path | None:
    """Retain an available minidump without discarding other crash evidence."""

    if minidump is None:
        return None
    try:
        return store.retain_attachment(run_id, minidump)
    except OSError:
        _LOGGER.exception(
            "Crashpad minidump could not be retained with its incident.",
            extra={"run_id": run_id},
        )
        return None


def _enrich_existing_incident(
    *,
    store: CrashIncidentStore,
    existing: CrashIncident,
    return_code: int,
    diagnostic_attachments: tuple[str, ...],
    runtime_context: CrashRunRuntimeContext,
    metadata: dict[str, str],
) -> CrashIncident:
    """Add supervisor evidence without replacing authoritative in-process facts."""

    attachments = tuple(
        filename
        for filename in (*existing.attachments, *diagnostic_attachments)
        if filename in diagnostic_attachments or Path(filename).suffix.lower() == ".dmp"
    )
    incident = replace(
        existing,
        exit_code=return_code,
        attachments=tuple(dict.fromkeys(attachments)),
        application_version=(
            existing.application_version or runtime_context.application_version
        ),
        platform=existing.platform or runtime_context.platform,
        python_version=existing.python_version or runtime_context.python_version,
        launch_arguments=existing.launch_arguments or runtime_context.launch_arguments,
        metadata={**existing.metadata, **metadata},
    )
    store.record(incident)
    return incident


def _synthesized_termination(
    *,
    minidump: Path | None,
    fault_log: Path,
    return_code: int,
    termination: SupervisedTermination,
) -> tuple[CrashKind, CrashBoundary, CrashAttribution, str]:
    """Classify durable termination evidence without guessing from generic exits."""

    if termination.is_startup_failure:
        return (
            CrashKind.STARTUP,
            CrashBoundary.SUPERVISOR,
            CrashAttribution.CONFIRMED,
            "SugarSubstitute did not complete startup before its process ended.",
        )
    aborted = _fault_log_reports_abort(fault_log) or return_code == -signal.SIGABRT
    if aborted:
        return (
            CrashKind.ABORT,
            CrashBoundary.NATIVE_HANDLER
            if minidump is not None
            else CrashBoundary.SUPERVISOR,
            CrashAttribution.CONFIRMED,
            "SugarSubstitute aborted after a fatal runtime failure.",
        )
    if minidump is not None:
        return (
            CrashKind.NATIVE,
            CrashBoundary.NATIVE_HANDLER,
            CrashAttribution.CONFIRMED,
            "Crashpad captured a native SugarSubstitute crash.",
        )
    return (
        CrashKind.ABNORMAL_EXIT,
        CrashBoundary.SUPERVISOR,
        CrashAttribution.UNCLEAN_TERMINATION,
        "SugarSubstitute terminated without a clean shutdown receipt.",
    )


def _fault_log_reports_abort(path: Path) -> bool:
    """Return whether bounded fatal evidence explicitly identifies an abort."""

    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - (1024 * 1024)))
            tail = stream.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    return "Fatal Python error: Aborted" in tail


def _meaningful_attachments(
    *,
    fault_log: Path,
    startup_output: Path,
    retained_dump: Path | None,
) -> tuple[str, ...]:
    """Return only attachments carrying evidence rather than empty placeholders."""

    attachments = [
        path.name
        for path in (fault_log, startup_output)
        if _file_has_non_whitespace(path)
    ]
    if retained_dump is not None:
        attachments.append(retained_dump.name)
    return tuple(dict.fromkeys(attachments))


def _file_has_non_whitespace(path: Path) -> bool:
    """Return whether a bounded sample contains meaningful text or binary evidence."""

    try:
        with path.open("rb") as stream:
            head = stream.read(4096)
            if any(not chr(byte).isspace() for byte in head):
                return True
            stream.seek(0, 2)
            size = stream.tell()
            if size <= len(head):
                return False
            stream.seek(max(0, size - 4096))
            return any(not chr(byte).isspace() for byte in stream.read())
    except OSError:
        return False


def _termination_metadata(
    *,
    termination: SupervisedTermination,
    exit_evidence: CleanExitEvidence,
    runtime_context_source: str,
    fault_log: Path,
    startup_output: Path,
) -> dict[str, str]:
    """Build actionable lifecycle and evidence facts for a durable incident."""

    metadata = {
        "termination_reason": termination.reason.value,
        "exit_intent_state": exit_evidence.intent_state.value,
        "exit_receipt_state": exit_evidence.receipt_state.value,
        "runtime_context_source": runtime_context_source,
        "python_fault_log": (
            "captured" if _file_has_non_whitespace(fault_log) else "empty_or_missing"
        ),
        "startup_output": (
            "captured"
            if _file_has_non_whitespace(startup_output)
            else "empty_or_missing"
        ),
    }
    if exit_evidence.intent is not None:
        metadata["exit_intent_outcome"] = exit_evidence.intent[0].value
    if exit_evidence.receipt is not None:
        metadata["exit_receipt_outcome"] = exit_evidence.receipt[0].value
    if termination.detail:
        metadata["termination_detail"] = termination.detail
    return metadata


__all__ = ["newest_run_minidump", "resolve_process_incident"]
