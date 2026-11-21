// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// What keeps the plugin from harming the iDrive UI, plus the one file-backed setting the demo menu exposes.
// Files in /var/local/data/HelloPlugin:
//   app.disable   present: the plugin stays off (the HMI starts without it). Set by hand for recovery.
//   app-guard     crash guard: one line per load; 3 loads that did not reach 2 minutes of uptime (an HMI crash
//                 loop) and create() refuses. Removed once the HMI has been up 2 minutes with the plugin.
//   demo-setting  the menu checkbox, stored as a file (present = on).
#ifndef HELLOPLUGIN_APP_GUARDS_HPP
#define HELLOPLUGIN_APP_GUARDS_HPP

namespace hello {
namespace app {

// Checked when the HMI creates the app; each logs why it keeps the plugin off.
bool appDisabled();       // app.disable present
bool crashGuardAllows();  // counts this load; false after 3 loads without 2 minutes of uptime

// Once per status poll, initTime being monoSeconds() when onInit ran (0 before): clears the crash guard once the
// HMI has run for 2 minutes with the plugin, i.e. it is not in a crash loop.
void resetGuardsWhenStable(long initTime);

// The demo checkbox, as a file.
bool settingOn();
void toggleSetting();

}  // namespace app
}  // namespace hello

#endif
