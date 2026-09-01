// SugarSubstitute - The desktop native Qt front-end for ComfyUI
// Copyright (C) 2026 Artificial Sweetener and contributors
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// Expose the small stable ABI used to initialize Crashpad from Python.

#include <map>
#include <memory>
#include <string>
#include <vector>

#include "base/files/file_path.h"
#include "build/build_config.h"
#include "client/crashpad_client.h"

#if BUILDFLAG(IS_WIN)
#include "base/strings/utf_string_conversions.h"
#define SUGAR_CRASHPAD_EXPORT __declspec(dllexport)
#else
#define SUGAR_CRASHPAD_EXPORT __attribute__((visibility("default")))
#endif

namespace {

crashpad::CrashpadClient* g_client = nullptr;

base::FilePath FilePathFromUtf8(const char* path) {
#if BUILDFLAG(IS_WIN)
  return base::FilePath(base::UTF8ToWide(path));
#else
  return base::FilePath(path);
#endif
}

}  // namespace

extern "C" SUGAR_CRASHPAD_EXPORT int SugarSubstituteCrashpadStart(
    const char* handler_path,
    const char* database_path,
    const char* metrics_path,
    const char* attachment_path,
    const char* application_version,
    const char* run_id) {
  if (g_client || !handler_path || !database_path || !metrics_path ||
      !application_version || !run_id) {
    return 0;
  }

  std::map<std::string, std::string> annotations = {
      {"product", "SugarSubstitute"},
      {"version", application_version},
      {"run_id", run_id},
  };
  std::vector<base::FilePath> attachments;
  if (attachment_path && attachment_path[0] != '\0') {
    attachments.emplace_back(FilePathFromUtf8(attachment_path));
  }

  auto client = std::make_unique<crashpad::CrashpadClient>();
  const bool started = client->StartHandler(
      FilePathFromUtf8(handler_path), FilePathFromUtf8(database_path),
      FilePathFromUtf8(metrics_path), std::string(), annotations,
      std::vector<std::string>(), true, false, attachments);
  if (!started) {
    return 0;
  }
  g_client = client.release();
  return 1;
}
