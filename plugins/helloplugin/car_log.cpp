// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// The read-only CDS logger (car_log.hpp).
#include "car_log.hpp"

#include <stddef.h>

#include "app_log.hpp"
#include "contract.hpp"

namespace hello {
namespace app {

namespace {

// A starter list from cds-properties.txt. Read-only; extend it freely. Names are "group.property" as the unit
// knows them (the subscription call takes the full dotted name).
const char* const kProperties[] = {
    "driving.gear",           "driving.speedDisplayed",     "driving.speedActual",
    "driving.odometer",       "driving.parkingBrake",       "driving.averageConsumption",
    "engine.RPMSpeed",        "engine.temperature",         "engine.rangeCalc",
    "sensors.fuel",           "sensors.temperatureExterior", "sensors.temperatureInterior",
    "sensors.doors",          "sensors.trunk",              "sensors.seatbelt",
    "vehicle.units",          "vehicle.VIN",                "vehicle.country",
    "vehicle.dayNightChangeOver",
};
const size_t kPropertyCount = sizeof(kProperties) / sizeof(kProperties[0]);

// One stub serves every property: addCdsHandler gives it the property name as `object`, so the log line can name it.
// Only logs on change (the framework may re-send the same value).
bool onCds(void* object, const bmw::BasicString<unsigned short>& value) {
    const char* name = static_cast<const char*>(object);
    char text[256];
    narrow(value, text, sizeof(text));
    logfile(contract::kCdsLog, contract::kCdsLogOld, "cds", "%s = %s", name ? name : "(null)", text);
    return true;
}

}  // namespace

void subscribeCdsLog(bmw::PluginApp* app) {
    alog("cds logger: subscribing to %d properties -> %s", static_cast<int>(kPropertyCount), contract::kCdsLog);
    for (size_t i = 0; i < kPropertyCount; ++i) {
        addCdsHandler(app, kProperties[i], &onCds, const_cast<char*>(kProperties[i]));
    }
}

}  // namespace app
}  // namespace hello
