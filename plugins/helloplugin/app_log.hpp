// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// The plugin's log writer. Lines carry a date, the monotonic clock and a tag, are bounded (the file rolls to
// <name>.old at 512 KiB) and are only written while the maintenance profile is present (log_profile.hpp).
#ifndef HELLOPLUGIN_APP_LOG_HPP
#define HELLOPLUGIN_APP_LOG_HPP

// The build's name in the logs. No build date: identical code gives the same .so, so an update can tell whether
// the head unit actually needs a restart.
#define HELLO_APP_VERSION "helloplugin-app-1"

namespace hello {
namespace app {

// One line into /var/local/data/HelloPlugin/app.log, tag [HelloPlugin]. Safe from any thread.
void alog(const char* fmt, ...) __attribute__((format(printf, 1, 2)));

// The same bounded, maintenance-gated writer against an arbitrary file and tag (used by the CDS logger).
void logfile(const char* path, const char* oldPath, const char* tag, const char* fmt, ...)
    __attribute__((format(printf, 4, 5)));

}  // namespace app
}  // namespace hello

#endif
