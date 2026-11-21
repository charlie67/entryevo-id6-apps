// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// Time since the head unit started, for delays: the car's wall-clock date can jump (GPS), this clock cannot.
#ifndef HELLOPLUGIN_MONO_CLOCK_HPP
#define HELLOPLUGIN_MONO_CLOCK_HPP

#include <time.h>

namespace hello {
namespace app {

inline long monoMs() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<long>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}
inline long monoSeconds() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<long>(ts.tv_sec);
}

}  // namespace app
}  // namespace hello

#endif
