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

"""Register every reviewed raw crash-relevant runtime boundary."""

from __future__ import annotations


CrashBoundaryInventoryRow = tuple[str, str, str, str, int, str]

# Keep one stable row per reviewed site so additions remain obvious in review.
# fmt: off
REVIEWED_CRASH_BOUNDARY_ROWS: tuple[CrashBoundaryInventoryRow, ...] = (
    ("application", "launcher/sugarsubstitute_launcher/app.py", "_run_launcher_window", "PySide6.QtWidgets.QApplication", 1, "supervised_launcher_ui"),
    ("application", "launcher/sugarsubstitute_launcher/crash_reporter.py", "_present_crash_incident", "PySide6.QtWidgets.QApplication", 1, "recovery_bound_crash_reporter"),
    ("application", "substitute/app/bootstrap/shared_splash_host.py", "main", "PySide6.QtWidgets.QApplication", 1, "isolated_support_ui"),
    ("application", "substitute/app/bootstrap/splash_process.py", "main", "PySide6.QtWidgets.QApplication", 1, "isolated_support_ui"),
    ("application", "substitute/devtools/prompt_editor_performance/qt_app.py", "prompt_performance_application", "PySide6.QtWidgets.QApplication", 1, "developer_only_ui"),
    ("application_class", "substitute/app/bootstrap/crash_aware_application.py", "CrashAwareApplication", "PySide6.QtWidgets.QApplication", 1, "process_crash_runtime"),
    ("executor", "substitute/infrastructure/execution/parallel_map.py", "BoundedParallelMapper.__enter__", "concurrent.futures.ThreadPoolExecutor", 1, "bounded_observed_futures"),
    ("executor", "substitute/infrastructure/execution/thread_pool_admission.py", "ThreadPoolAdmission.__init__", "concurrent.futures.ThreadPoolExecutor", 1, "managed_task_outcomes"),
    ("process", "launcher/sugarsubstitute_launcher/crash_reporter.py", "_restart_application", "subprocess.Popen", 1, "supervised_restart_launcher"),
    ("process", "launcher/sugarsubstitute_launcher/process.py", "spawn_detached_process", "subprocess.Popen", 1, "application_supervisor_adapter"),
    ("process", "launcher/sugarsubstitute_launcher/runtime_command.py", "SubprocessRuntimeCommandRunner.run", "subprocess.Popen", 1, "external_install_command"),
    ("process", "substitute/app/bootstrap/early_launch_splash.py", "start_shared_launch_splash", "subprocess.Popen", 1, "isolated_support_process"),
    ("process", "substitute/infrastructure/comfy/managed_install_commands.py", "stream_command", "subprocess.Popen", 1, "external_comfy_command"),
    ("process", "substitute/infrastructure/comfy/posix_guardian_containment.py", "launch_with_guardian", "subprocess.Popen", 1, "external_comfy_guardian"),
    ("process", "substitute/infrastructure/comfy/posix_guardian_entry.py", "main", "subprocess.Popen", 1, "external_comfy_process"),
    ("process", "substitute/infrastructure/comfy/standalone_environment/extraction_process.py", "NativeSevenZipExtractionProcess.extract", "subprocess.Popen", 1, "external_extraction_tool"),
    ("process", "substitute/infrastructure/external/native_file_manager_gateway.py", "_launch_process", "subprocess.Popen", 1, "operating_system_shell"),
    ("process", "substitute/infrastructure/process/hidden_process_runner.py", "stream_command", "subprocess.Popen", 1, "external_tool_process"),
    ("process", "substitute/infrastructure/process/hidden_process_runner.py", "stream_command_collecting_output", "subprocess.Popen", 1, "external_tool_process"),
    ("process", "sugarsubstitute_shared/launcher_update/process.py", "schedule_launcher_update", "subprocess.Popen", 1, "transactional_launcher_handoff"),
    ("process", "sugarsubstitute_shared/launcher_update/transaction.py", "_relaunch", "subprocess.Popen", 1, "supervised_launcher_handoff"),
    ("process", "launcher/sugarsubstitute_launcher/dev_install.py", "_run_runtime_script", "subprocess.run", 1, "external_runtime_install_command"),
    ("process", "launcher/sugarsubstitute_launcher/managed_comfy_repair.py", "SubprocessManagedComfyRepairCommandRunner.run", "subprocess.run", 1, "external_comfy_command"),
    ("process", "substitute/infrastructure/comfy/hardware_linux.py", "_parse_lspci_output", "subprocess.run", 1, "external_hardware_probe"),
    ("process", "substitute/infrastructure/comfy/hardware_windows.py", "_read_windows_cim_adapters", "subprocess.run", 1, "external_hardware_probe"),
    ("process", "substitute/infrastructure/comfy/intel_xpu_detection.py", "read_intel_xpu_adapters", "subprocess.run", 1, "external_hardware_probe"),
    ("process", "substitute/infrastructure/comfy/managed_environment_validator.py", "run_command", "subprocess.run", 1, "external_environment_validation"),
    ("process", "substitute/infrastructure/comfy/managed_install_commands.py", "pip_install", "subprocess.run", 1, "external_comfy_install_command"),
    ("process", "substitute/infrastructure/comfy/managed_install_commands.py", "run_command", "subprocess.run", 1, "external_comfy_command"),
    ("process", "substitute/infrastructure/comfy/managed_process_query.py", "_run_query", "subprocess.run", 1, "external_process_query"),
    ("process", "substitute/infrastructure/comfy/managed_shutdown.py", "_kill_windows_process", "subprocess.run", 1, "external_process_control"),
    ("process", "substitute/infrastructure/comfy/managed_shutdown.py", "_posix_descendants", "subprocess.run", 1, "external_process_query"),
    ("process", "substitute/infrastructure/comfy/managed_shutdown.py", "_signal_posix", "subprocess.run", 1, "external_process_control"),
    ("process", "substitute/infrastructure/comfy/manager_requirements_installer.py", "ComfyManagerRequirementsInstaller._install", "subprocess.run", 1, "external_comfy_install_command"),
    ("process", "substitute/infrastructure/comfy/manager_runtime_probe.py", "ComfyManagerRuntimeProbe._run", "subprocess.run", 1, "external_comfy_probe"),
    ("process", "substitute/infrastructure/comfy/nvidia_detection.py", "read_nvidia_smi_adapters", "subprocess.run", 1, "external_hardware_probe"),
    ("process", "substitute/infrastructure/comfy/python_policy.py", "_probe_python_executable", "subprocess.run", 1, "external_python_probe"),
    ("process", "substitute/infrastructure/comfy/python_requirements_probe.py", "PythonRequirementsProbe.assess", "subprocess.run", 1, "external_python_probe"),
    ("process", "substitute/infrastructure/comfy/standalone_environment/environment_builder.py", "StandaloneVirtualEnvironmentBuilder.build", "subprocess.run", 1, "external_environment_command"),
    ("process", "substitute/infrastructure/comfy/standalone_environment/extraction_process.py", "_run_bounded", "subprocess.run", 1, "external_extraction_tool"),
    ("process", "substitute/infrastructure/comfy/standalone_environment/tar_extraction_process.py", "NativeTarExtractionProcess.extract", "subprocess.run", 1, "external_extraction_tool"),
    ("process", "substitute/infrastructure/comfy/workspace_python_discovery.py", "probe_comfy_python", "subprocess.run", 1, "external_python_probe"),
    ("process", "substitute/infrastructure/onboarding/launcher_managed_runtime_provisioner.py", "LauncherManagedRuntimeProvisioner._run_checked", "subprocess.run", 1, "external_runtime_provisioning"),
    ("process", "substitute/infrastructure/onboarding/substitute_runtime_provisioner.py", "SubstituteRuntimeProvisioner._run_checked", "subprocess.run", 1, "external_runtime_provisioning"),
    ("process", "substitute/infrastructure/onboarding/substitute_runtime_provisioner.py", "SubstituteRuntimeProvisioner._runtime_has_pip", "subprocess.run", 1, "external_python_probe"),
    ("process", "substitute/infrastructure/process/hidden_process_runner.py", "run_command", "subprocess.run", 1, "external_tool_process"),
    ("process", "substitute/infrastructure/version_control/clone_process.py", "Pygit2CloneProcess.clone", "subprocess.run", 1, "external_version_control_command"),
    ("python_crash_hook", "sugarsubstitute_shared/crash_reporting/runtime.py", "ProcessCrashRuntime.install", "sys.excepthook", 1, "authoritative_crash_hook"),
    ("python_crash_hook", "sugarsubstitute_shared/crash_reporting/runtime.py", "ProcessCrashRuntime.install", "sys.unraisablehook", 1, "authoritative_crash_hook"),
    ("python_crash_hook", "sugarsubstitute_shared/crash_reporting/runtime.py", "ProcessCrashRuntime.install", "threading.excepthook", 1, "authoritative_crash_hook"),
    ("crash_hook", "substitute/app/bootstrap/lifecycle.py", "register_signal_handlers", "signal.signal", 1, "graceful_shutdown_signal"),
    ("crash_hook", "substitute/app/bootstrap/lifecycle.py", "register_signal_handlers", "signal.signal", 2, "graceful_shutdown_signal"),
    ("crash_hook", "substitute/infrastructure/comfy/posix_guardian_entry.py", "_install_signal_handlers", "signal.signal", 1, "external_guardian_shutdown_signal"),
    ("crash_hook", "substitute/infrastructure/comfy/posix_guardian_entry.py", "_install_signal_handlers", "signal.signal", 2, "external_guardian_shutdown_signal"),
    ("crash_hook", "sugarsubstitute_shared/crash_reporting/runtime.py", "ProcessCrashRuntime._enable_fault_handler", "faulthandler.enable", 1, "authoritative_fault_trace"),
    ("qt_fatal_hook", "substitute/app/bootstrap/qt_message_trace.py", "install_qt_message_trace_handler", "PySide6.QtCore.qInstallMessageHandler", 1, "authoritative_qt_hook_probe"),
    ("qt_fatal_hook", "substitute/app/bootstrap/qt_message_trace.py", "install_qt_message_trace_handler", "PySide6.QtCore.qInstallMessageHandler", 2, "authoritative_qt_hook_install"),
    ("hard_exit", "launcher/sugarsubstitute_launcher/__main__.py", "<module>", "builtins.SystemExit", 1, "controlled_launcher_entrypoint_exit"),
    ("hard_exit", "launcher/sugarsubstitute_launcher/dev_install.py", "<module>", "builtins.SystemExit", 1, "controlled_developer_entrypoint_exit"),
    ("hard_exit", "launcher/sugarsubstitute_launcher/repair_entrypoint.py", "<module>", "builtins.SystemExit", 1, "controlled_launcher_entrypoint_exit"),
    ("hard_exit", "main.py", "_run_entrypoint", "builtins.SystemExit", 1, "source_supervisor_outcome"),
    ("hard_exit", "main.py", "main", "sys.exit", 1, "supervised_clean_exit"),
    ("hard_exit", "substitute/app/bootstrap/lifecycle.py", "register_signal_handlers", "sys.exit", 1, "graceful_shutdown_exit"),
    ("hard_exit", "substitute/app/bootstrap/lifecycle.py", "register_signal_handlers", "sys.exit", 2, "graceful_shutdown_exit"),
    ("hard_exit", "substitute/app/bootstrap/shared_splash_host.py", "<module>", "builtins.SystemExit", 1, "isolated_support_entrypoint"),
    ("hard_exit", "substitute/app/bootstrap/splash_process.py", "<module>", "builtins.SystemExit", 1, "isolated_support_entrypoint"),
    ("hard_exit", "substitute/app/bootstrap/splash_process.py", "parent_process_is_alive", "os.kill", 1, "parent_liveness_probe"),
    ("hard_exit", "substitute/app/maintenance/__main__.py", "<module>", "builtins.SystemExit", 1, "isolated_support_entrypoint"),
    ("hard_exit", "substitute/infrastructure/comfy/managed_process_probe.py", "is_process_running", "os.kill", 1, "external_process_liveness_probe"),
    ("hard_exit", "substitute/infrastructure/comfy/posix_guardian_containment.py", "request_guardian_stop_by_pid", "os.kill", 1, "external_guardian_control"),
    ("hard_exit", "substitute/infrastructure/comfy/posix_guardian_entry.py", "<module>", "builtins.SystemExit", 1, "external_guardian_entrypoint"),
    ("hard_exit", "substitute/infrastructure/version_control/clone_entry.py", "<module>", "builtins.SystemExit", 1, "isolated_clone_entrypoint"),
    ("hard_exit", "sugarsubstitute_shared/launcher_update/helper.py", "<module>", "builtins.SystemExit", 1, "transactional_update_entrypoint"),
    ("hard_exit", "sugarsubstitute_shared/launcher_update/helper.py", "main", "builtins.SystemExit", 1, "transactional_update_handoff"),
    ("hard_exit", "sugarsubstitute_shared/launcher_update/transaction.py", "_process_exists", "os.kill", 1, "process_liveness_probe"),
    ("qt_thread", "launcher/sugarsubstitute_launcher/ui/installation_execution.py", "QtInstallationExecutor.start_initial", "PySide6.QtCore.QThread", 1, "signal_reported_install_worker"),
    ("qt_thread", "launcher/sugarsubstitute_launcher/ui/installation_execution.py", "QtInstallationExecutor.start_setup", "PySide6.QtCore.QThread", 1, "signal_reported_install_worker"),
    ("qt_thread", "launcher/sugarsubstitute_launcher/ui/repair_preparation_execution.py", "QtRepairPreparationExecutor.start", "PySide6.QtCore.QThread", 1, "signal_reported_install_worker"),
    ("qt_thread", "substitute/presentation/shell/empty_model_picker_discovery_controller.py", "EmptyModelPickerDiscoveryController._start", "PySide6.QtCore.QThread", 1, "managed_task_outcomes"),
    ("qt_thread", "substitute/presentation/shell/model_update_notification_controller.py", "ModelUpdateNotificationController._start", "PySide6.QtCore.QThread", 1, "managed_task_outcomes"),
    ("thread", "launcher/sugarsubstitute_launcher/splash_session.py", "_readline_with_timeout", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "launcher/sugarsubstitute_launcher/splash_session.py", "_start_background_pipe_reader", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "sugarsubstitute_shared/application_instance_broker.py", "ApplicationInstanceBroker.__init__", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "sugarsubstitute_shared/application_instance_broker.py", "ApplicationInstanceBroker._accept_connections", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "sugarsubstitute_shared/application_instance_macos.py", "MacOSMessagePortClaim.__init__", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "sugarsubstitute_shared/application_supervisor_client.py", "ApplicationSupervisorClient.__init__", "threading.Thread", 1, "bounded_transport_thread"),
    ("thread", "substitute/infrastructure/comfy/posix_guardian_entry.py", "_start_control_monitor", "threading.Thread", 1, "external_guardian_thread"),
    ("thread", "substitute/infrastructure/comfy/posix_guardian_entry.py", "_start_output_forwarder", "threading.Thread", 1, "external_guardian_thread"),
    ("thread", "substitute/infrastructure/execution/host_execution_diagnostics.py", "HostExecutionDiagnostics.subscribe", "threading.Thread", 1, "managed_host_diagnostics"),
    ("thread", "substitute/infrastructure/execution/host_execution_scheduler.py", "HostExecutionScheduler._ensure_workers_locked", "threading.Thread", 1, "managed_host_scheduler"),
    ("thread", "substitute/infrastructure/execution/host_execution_scheduler.py", "HostExecutionScheduler._ensure_workers_locked", "threading.Thread", 2, "managed_host_scheduler"),
    ("thread", "substitute/infrastructure/execution/long_lived_task.py", "LongLivedTaskHandle.__init__", "threading.Thread", 1, "managed_task_outcomes"),
    ("thread", "substitute/infrastructure/execution/process_output.py", "BinaryProcessOutput.__init__", "threading.Thread", 1, "bounded_process_output"),
    ("thread", "sugarsubstitute_shared/launch_splash/server.py", "SplashSessionServer.start", "threading.Thread", 1, "bounded_transport_thread"),
)
# fmt: on


__all__ = ["CrashBoundaryInventoryRow", "REVIEWED_CRASH_BOUNDARY_ROWS"]
