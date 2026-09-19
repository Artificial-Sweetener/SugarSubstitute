// SugarSubstitute - The desktop native Qt front-end for ComfyUI
// Copyright (C) 2026 Artificial Sweetener and contributors
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// Qualify the shipped bridge with a real native access violation.

#include <filesystem>
#include <chrono>
#include <string_view>
#include <thread>

#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace {

using StartFunction = int (*)(const char*, const char*, const char*, const char*,
                              const char*, const char*);

StartFunction LoadStartFunction(const char* library_path) {
#if defined(_WIN32)
  const std::filesystem::path path = std::filesystem::u8path(library_path);
  HMODULE library = LoadLibraryW(path.c_str());
  return library ? reinterpret_cast<StartFunction>(
                       GetProcAddress(library, "SugarSubstituteCrashpadStart"))
                 : nullptr;
#else
  void* library = dlopen(library_path, RTLD_NOW | RTLD_LOCAL);
  return library ? reinterpret_cast<StartFunction>(
                       dlsym(library, "SugarSubstituteCrashpadStart"))
                 : nullptr;
#endif
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 5 && argc != 6) {
    return 2;
  }
  const StartFunction start = LoadStartFunction(argv[1]);
  if (!start || start(argv[2], argv[3], argv[4], "", "qualification", "probe") !=
                    1) {
    return 3;
  }
  if (argc == 6 && std::string_view(argv[5]) == "--idle") {
    std::this_thread::sleep_for(std::chrono::minutes(5));
    return 0;
  }
  volatile int* invalid_address = nullptr;
  *invalid_address = 42;
  return 4;
}
