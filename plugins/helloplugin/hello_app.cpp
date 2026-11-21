// Copyright (c) 2026 Charlie Robinson
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
//
// libHelloPlugin.so: a minimal native iDrive "PluginApp" for a rooted BMW EntryEVO (ID5/ID6) head unit, built with
// the same framework as BMW's SecurityMenu / ActiveSeating and loaded directly into HmiMain3D. It is a hello-world
// skeleton: an entry row in the My Vehicle menu that opens a small menu with
//   - a label whose text is set at runtime with updateModel(id, const char*)  (the first new framework call tried),
//   - a "Change message" button that cycles that text,
//   - a demo checkbox stored as a file,
//   - a Help child state reached through an hmiAction,
// a 1-second status poll (postRunnable) that refreshes the label, and a read-only CDS logger (car_log.cpp).
//
// Everything runs INSIDE HmiMain3D, so a crash or a stall kills the iDrive UI (systemd WatchdogSec 75 s). The code
// is tiny, never blocks on the HMI thread, and is protected by an off switch and a crash guard (app_guards.cpp).
//
// Loading, as reverse-engineered on the copied rootfs (firmware 202402191339):
//   - HmiMain3D scans /opt/hmi/data/ro/Plugins at boot; that folder is not coding-gated on this firmware.
//   - ManagedPluginApp::init dlopen's libHelloPlugin.so, dlsym's "pluginAppInfo" (the one exported symbol), then
//     calls create() at +0x10; destroy() is at +0x14.
//   - The entry row goes in the My Vehicle menu (ST_MyV_Selection), native state 60 (0x3c) on this firmware
//     (CHmiCarApplication::getSelectionState; cross-checked against Media/ST_Ent_Selection = 20).
// Uninstall: delete /opt/hmi/data/ro/Plugins/HelloPlugin and reboot.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "app_guards.hpp"
#include "app_log.hpp"
#include "bmw_framework.hpp"
#include "car_log.hpp"
#include "contract.hpp"
#include "hello_ids.hpp"
#include "mono_clock.hpp"

namespace hello {
namespace app {

namespace {

const unsigned kStatusPollMs = 1000;

bmw::PluginApp* g_app = nullptr;     // created by HmiMain3D, until destroyed
bmw::PluginApp* g_runApp = nullptr;  // initialized, until finalized: the posted tasks run while it is set
long g_initTime = 0;                 // monoSeconds() when onInit ran
unsigned g_message = 0;              // index into kMessages, advanced by the button
unsigned g_presses = 0;              // how many times the button has been pressed

const char* const kMessages[] = {
    "Hello, world!",
    "updateModel(const char*) works",
    "Running inside HmiMain3D",
    "Press MENU to go back",
};
const unsigned kMessageCount = sizeof(kMessages) / sizeof(kMessages[0]);

// ---- the free-text label --------------------------------------------------------------------------------------------
// Builds the label text and pushes it with updateModel(id, const char*): "<message>  (up <N>s, presses <M>)".
void refreshLabel(bmw::PluginApp* app) {
    char text[160];
    snprintf(text, sizeof(text), "%s  (up %lds, presses %u)", kMessages[g_message % kMessageCount],
             g_initTime ? (monoSeconds() - g_initTime) : 0L, g_presses);
    app->updateModel(kLabelModel, text);
}

void showSetting(bmw::PluginApp* app) {
    app->updateModel(kSettingModel, settingOn());
}

// ---- handlers -------------------------------------------------------------------------------------------------------
// Entry button "Hello World" in the iDrive Media menu: open the plugin's own menu.
bool onEntry(void* self, const bmw::Parcel&) {
    bmw::PluginApp* app = static_cast<bmw::PluginApp*>(self);
    alog("entry: Hello World selected");
    app->triggerEvent(kEvOpenMenu);
    return true;
}

// "Change message": advance the label text and refresh it at once.
bool onChangeMessage(void*, const bmw::Parcel&) {
    g_message = (g_message + 1) % kMessageCount;
    ++g_presses;
    alog("menu: Change message -> \"%s\" (press %u)", kMessages[g_message], g_presses);
    if (g_runApp) {
        refreshLabel(g_runApp);
    }
    return true;
}

// The demo checkbox: toggle the file, then show the stored state back.
bool onSettingToggle(void*, const bmw::Parcel&) {
    toggleSetting();
    if (g_runApp) {
        showSetting(g_runApp);
    }
    return true;
}

// Menu focused: refresh what the menu shows (label text and the checkbox).
bool onMenuFocus(void*, const bmw::Parcel& p) {
    if (parcelBool(p) && g_runApp) {
        showSetting(g_runApp);
        refreshLabel(g_runApp);
    }
    return true;
}

// ---- the 1-second status poll ---------------------------------------------------------------------------------------
AppRunnable g_statusRunnable;
void statusRun(void*) {
    bmw::PluginApp* app = g_runApp;
    if (!app) {
        return;
    }
    resetGuardsWhenStable(g_initTime);
    refreshLabel(app);
    postRunnable(app, g_statusRunnable, kStatusPollMs);
}

// ---- the CDS logger, subscribed shortly after the app runs ----------------------------------------------------------
AppRunnable g_subRunnable;
void subscribeRun(void*) {
    if (g_runApp) {
        subscribeCdsLog(g_runApp);
    }
}

// ---- the app object -------------------------------------------------------------------------------------------------
bool appOnInit(bmw::PluginApp* self) {
    alog("onInit: begin");
    addAction(self, kActEntry, &onEntry);
    addAction(self, kActChange, &onChangeMessage);
    addAction(self, kActSetting, &onSettingToggle);
    addStateHandler(self, kMenuState, kHandlerFocus, &onMenuFocus);
    g_initTime = monoSeconds();
    bool ok = self->onInit();
    alog("onInit: handlers registered, base onInit -> %d, demo setting %s", static_cast<int>(ok),
         settingOn() ? "on" : "off");
    g_runApp = self;
    makeRunnable(g_subRunnable, &subscribeRun);
    postRunnable(self, g_subRunnable, 1500);
    makeRunnable(g_statusRunnable, &statusRun);
    postRunnable(self, g_statusRunnable, 2000);
    return ok;
}

void appOnError(bmw::PluginApp*, unsigned code, const bmw::BasicString<char>& text) {
    const char* s = text.raw();
    alog("onError %u: %s", code, s ? s : "(null)");
}

void appOnFinalize(bmw::PluginApp* self) {
    alog("onFinalize");
    g_runApp = nullptr;
    self->onFinalize();
}

bmw::PluginApp* createApp(bmw::IDispatcher& dispatcher, const char* name, const bmw::Bundle& params,
                          const bmw::Bundle& config) {
    mkdir(contract::kDataDir, 0755);
    alog("create(name=%s) %s, HMI pid %d", name ? name : "(null)", HELLO_APP_VERSION, static_cast<int>(getpid()));
    if (appDisabled() || !crashGuardAllows()) {
        return nullptr;
    }
    if (g_app) {
        alog("create: already created");
        return nullptr;
    }
    const PluginAppHooks hooks = {&appOnInit, &appOnError, &appOnFinalize};
    void* base = nullptr;
    bmw::PluginApp* app = newPluginApp(dispatcher, name, params, config, hooks, &base);
    g_app = app;
    alog("create: app %p (PluginApp vtable %p)", static_cast<void*>(app), base);
    return app;
}

void destroyApp(void* app) {
    alog("destroy(%p)", app);
    if (!app) {
        return;
    }
    deletePluginApp(app);
    if (app == g_app) {
        g_app = nullptr;
    }
}

__attribute__((constructor)) void libraryLoaded() {
    mkdir(contract::kDataDir, 0755);
    alog("library loaded into pid %d, %s", static_cast<int>(getpid()), HELLO_APP_VERSION);
}

}  // namespace
}  // namespace app
}  // namespace hello

// What ManagedPluginApp::init reads with dlsym: create at +0x10, destroy at +0x14. The library's only exported symbol.
extern "C" {
struct HelloPluginAppInfo {
    uint16_t versionMajor;
    uint16_t versionMinor;
    const char* name;
    const char* vendor;
    uint32_t rhmiInterfaceVersion;
    bmw::PluginApp* (*create)(bmw::IDispatcher&, const char*, const bmw::Bundle&, const bmw::Bundle&);
    void (*destroy)(void*);
};
__attribute__((visibility("default"))) HelloPluginAppInfo pluginAppInfo = {
    1, 0, "Hello World", "HelloPlugin", 1, &hello::app::createApp, &hello::app::destroyApp};
}
