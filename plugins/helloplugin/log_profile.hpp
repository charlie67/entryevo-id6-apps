// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// By default the plugin keeps no log. The "maintenance profile" is one marker file on the data partition,
// created at installation or by hand; while it is present, the app and the CDS logger write their files.
#ifndef HELLOPLUGIN_LOG_PROFILE_HPP
#define HELLOPLUGIN_LOG_PROFILE_HPP
#include <unistd.h>

namespace hello {

inline bool maintenanceProfile(const char* marker) {
    return access(marker, F_OK) == 0;
}

}  // namespace hello

#endif
