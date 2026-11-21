// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// The off switch, the crash guard and the file-backed demo setting (app_guards.hpp).
#include "app_guards.hpp"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "app_log.hpp"
#include "contract.hpp"
#include "mono_clock.hpp"

namespace hello {
namespace app {

namespace {

const int kCrashGuardMax = 3;  // loads without 2 min of uptime before the plugin turns itself off
const long kStableAfterS = 120;

bool g_stableMarked = false;

bool fileExists(const char* p) {
    struct stat st;
    return stat(p, &st) == 0;
}

}  // namespace

bool appDisabled() {
    if (fileExists(contract::kAppDisable)) {
        alog("disabled by %s", contract::kAppDisable);
        return true;
    }
    return false;
}

// create() appends one line; 2 minutes later the status poll deletes the file. kCrashGuardMax lines means the HMI
// went down that many times shortly after loading us: create() then refuses and the iDrive starts without the plugin.
bool crashGuardAllows() {
    int lines = 0;
    FILE* f = fopen(contract::kAppGuard, "r");
    if (f) {
        char b[64];
        while (fgets(b, sizeof(b), f)) {
            ++lines;
        }
        fclose(f);
    }
    if (lines >= kCrashGuardMax) {
        alog(
            "crash guard: the HMI restarted %d times shortly after loading this plugin: plugin turned off. "
            "Remove %s after checking the logs, then restart the unit.",
            kCrashGuardMax, contract::kAppGuard);
        return false;
    }
    f = fopen(contract::kAppGuard, "a");
    if (f) {
        fprintf(f, "%ld\n", static_cast<long>(time(nullptr)));
        fflush(f);
        fsync(fileno(f));
        fclose(f);
    }
    return true;
}

void resetGuardsWhenStable(long initTime) {
    if (!g_stableMarked && initTime && monoSeconds() - initTime >= kStableAfterS) {
        g_stableMarked = true;
        unlink(contract::kAppGuard);  // the HMI has been up 2 min with us: not a crash loop
        alog("stable for %ld s: crash guard reset", kStableAfterS);
    }
}

bool settingOn() {
    return fileExists(contract::kSetting);
}

void toggleSetting() {
    bool on = settingOn();
    if (on) {
        if (unlink(contract::kSetting) != 0 && errno != ENOENT) {
            alog("setting: cannot remove %s (errno %d)", contract::kSetting, errno);
        }
    } else {
        int fd = open(contract::kSetting, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
        if (fd < 0) {
            alog("setting: cannot create %s (errno %d)", contract::kSetting, errno);
        } else {
            ssize_t w = write(fd, "1\n", 2);
            (void)w;
            fsync(fd);
            close(fd);
        }
    }
    alog("menu: demo setting %s -> %s", on ? "on" : "off", settingOn() ? "on" : "off");
}

}  // namespace app
}  // namespace hello
