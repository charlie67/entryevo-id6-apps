// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// A read-only CDS (Car Data Service) logger: subscribe to a list of properties and write each value to cds.log as
// it changes. It never writes to the car. Its purpose is to find out which properties this car actually fills and
// the exact JSON of each. Handlers run on the HMI thread, so they only narrow the text and append a line.
#ifndef HELLOPLUGIN_CAR_LOG_HPP
#define HELLOPLUGIN_CAR_LOG_HPP

#include "bmw_framework.hpp"

namespace hello {
namespace app {

// Subscribe the logger to every property in the built-in list. Call once, after the app is running.
void subscribeCdsLog(bmw::PluginApp* app);

}  // namespace app
}  // namespace hello

#endif
