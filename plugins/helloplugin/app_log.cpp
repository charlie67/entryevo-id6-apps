// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// The plugin's bounded, maintenance-gated log writer (app_log.hpp).
#include "app_log.hpp"

#include <fcntl.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "contract.hpp"
#include "log_profile.hpp"

namespace hello {
namespace app {

namespace {

pthread_mutex_t g_logMutex = PTHREAD_MUTEX_INITIALIZER;
const long kMaxBytes = 512 * 1024;

void vlogfile(const char* path, const char* oldPath, const char* tag, const char* fmt, va_list ap) {
    if (!maintenanceProfile(contract::kMaintenance)) {
        return;
    }
    char msg[384];
    vsnprintf(msg, sizeof(msg), fmt, ap);

    char line[512];
    time_t now = time(nullptr);
    struct tm tmv;
    localtime_r(&now, &tmv);
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    int n = snprintf(line, sizeof(line), "%04d-%02d-%02d %02d:%02d:%02d [%5ld.%03ld] [%s] %s\n", tmv.tm_year + 1900,
                     tmv.tm_mon + 1, tmv.tm_mday, tmv.tm_hour, tmv.tm_min, tmv.tm_sec, static_cast<long>(ts.tv_sec),
                     (ts.tv_nsec / 1000000), tag, msg);
    if (n < 0) {
        return;
    }
    if (n >= static_cast<int>(sizeof(line))) {
        n = static_cast<int>(sizeof(line)) - 1;
    }

    pthread_mutex_lock(&g_logMutex);
    struct stat st;
    if (stat(path, &st) == 0 && st.st_size > kMaxBytes) {
        rename(path, oldPath);  // persistent, bounded
    }
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    if (fd >= 0) {
        ssize_t w = write(fd, line, static_cast<size_t>(n));
        (void)w;
        close(fd);
    }
    pthread_mutex_unlock(&g_logMutex);
}

}  // namespace

void alog(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vlogfile(contract::kAppLog, contract::kAppLogOld, "HelloPlugin", fmt, ap);
    va_end(ap);
}

void logfile(const char* path, const char* oldPath, const char* tag, const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vlogfile(path, oldPath, tag, fmt, ap);
    va_end(ap);
}

}  // namespace app
}  // namespace hello
