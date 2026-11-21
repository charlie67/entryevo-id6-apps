// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
//
// Paths the HelloPlugin iDrive app uses. Code lives on the read-only system partition
// (/opt/hmi/data/ro/Plugins/HelloPlugin); settings and logs live on the writable data partition
// (/var/local/data/HelloPlugin), which survives reboots but is mounted noexec.
#ifndef HELLOPLUGIN_CONTRACT_HPP
#define HELLOPLUGIN_CONTRACT_HPP

namespace hello {
namespace contract {

// ---- install location (system partition, read-only except while installing) --------------------------------------
constexpr char kPluginDir[] = "/opt/hmi/data/ro/Plugins/HelloPlugin";

// ---- settings and logs (data partition, kept across restarts) -----------------------------------------------------
constexpr char kDataDir[] = "/var/local/data/HelloPlugin";
constexpr char kMaintenance[] = "/var/local/data/HelloPlugin/maintenance";   // present: the app keeps logs
constexpr char kAppLog[] = "/var/local/data/HelloPlugin/app.log";
constexpr char kAppLogOld[] = "/var/local/data/HelloPlugin/app.old.log";
constexpr char kAppDisable[] = "/var/local/data/HelloPlugin/app.disable";    // present: the app stays off (by hand)
constexpr char kAppGuard[] = "/var/local/data/HelloPlugin/app-guard";        // crash guard: 3 short HMI runs -> off
constexpr char kSetting[] = "/var/local/data/HelloPlugin/demo-setting";      // the menu checkbox, as a file
constexpr char kCdsLog[] = "/var/local/data/HelloPlugin/cds.log";            // the CDS logger's output
constexpr char kCdsLogOld[] = "/var/local/data/HelloPlugin/cds.old.log";

}  // namespace contract
}  // namespace hello

#endif
