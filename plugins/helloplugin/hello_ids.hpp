// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
// The ids of HelloPlugin.xml that the code uses. The XML is parsed by the car and is the source of truth: these
// values follow it, so edit both together.
#ifndef HELLOPLUGIN_HELLO_IDS_HPP
#define HELLOPLUGIN_HELLO_IDS_HPP

namespace hello {
namespace app {

// ---- hmiStates -----------------------------------------------------------------------------------------------------
const unsigned kMenuState = 10;  // the plugin's menu
const unsigned kHelpState = 12;  // "Help", child of the menu
// State handler kinds, as bmw::PluginApp::addHandler(state, kind, ...) takes them.
const unsigned kHandlerFocus = 1;

// ---- focusEvents ---------------------------------------------------------------------------------------------------
const unsigned kEvOpenMenu = 51;  // -> state 10 (the plugin's menu)

// ---- raActions -----------------------------------------------------------------------------------------------------
const unsigned kActEntry = 2;     // entry button "Hello World" (iDrive Media menu)
const unsigned kActChange = 21;   // "Change message" button
const unsigned kActSetting = 24;  // the demo checkbox

// ---- the entry button ----------------------------------------------------------------------------------------------
const unsigned kEntryTextModel = 3;  // textIdModel, static "Hello World"
const unsigned kImgEntryIcon = 56001;

// ---- the menu ------------------------------------------------------------------------------------------------------
const unsigned kLabelModel = 30;    // raDataModel: free text set with updateModel(id, const char*)
const unsigned kSettingModel = 34;  // raBoolModel: the demo checkbox value

}  // namespace app
}  // namespace hello

#endif
