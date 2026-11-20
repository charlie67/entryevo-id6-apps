/* plugin_load_check - RHMI plugin pre-ship load/ABI check, run under QEMU against the car's
 * dumped libraries. Mirrors what HmiMain3D's ManagedPluginApp::init does, WITHOUT calling
 * create() (that needs HmiMain3D's live dispatcher).
 *
 * Checks:
 *   1. The car's libAppFramework.A.so loads (RTLD_NOW -> surfaces unresolved framework symbols).
 *   2. Firmware invariants: bmw::PluginApp vtable has onError/onInit/onFinalize at slots 21/22/23
 *      (the slots a plugin patches), and bmw::Runnable's vtable exists (used by posted tasks).
 *   3. If a plugin .so is given: it loads (RTLD_NOW -> surfaces the plugin's undefined symbols
 *      against the real firmware), exports exactly "pluginAppInfo", and that struct is well formed
 *      (version 1.0, rhmiInterfaceVersion 1, non-null create/destroy, readable name).
 *
 * Usage: plugin_load_check [plugin.so]
 * Exit 0 = PASS. Build as C (plain libc + libdl); no libstdc++ dependency of its own.
 */
#define _GNU_SOURCE /* for RTLD_DEFAULT */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int fails = 0;
#define OK(cond, msg)                                       \
    do {                                                    \
        if (cond) {                                         \
            printf("  [ok]   %s\n", msg);                   \
        } else {                                            \
            printf("  [FAIL] %s\n", msg);                   \
            fails++;                                        \
        }                                                   \
    } while (0)

int main(int argc, char **argv) {
    const char *plugin = argc > 1 ? argv[1] : NULL;
    printf("== plugin_load_check ==\n");

    /* 1. framework */
    printf("[1] car framework libAppFramework.A.so\n");
    void *fw = dlopen("libAppFramework.A.so", RTLD_NOW | RTLD_GLOBAL);
    if (!fw) {
        printf("  [FAIL] dlopen libAppFramework.A.so: %s\n", dlerror());
        printf("RESULT: FAIL (framework did not load)\n");
        return 1;
    }
    printf("  [ok]   loaded\n");

    /* 2. firmware invariants */
    printf("[2] bmw::PluginApp vtable slots (21/22/23) on THIS firmware\n");
    void **vt = (void **)dlsym(fw, "_ZTVN3bmw9PluginAppE");
    void *onError = dlsym(fw, "_ZN3bmw9PluginApp7onErrorEjRKNS_11BasicStringIcEE");
    void *onInit = dlsym(fw, "_ZN3bmw9PluginApp6onInitEv");
    void *onFinalize = dlsym(fw, "_ZN3bmw9PluginApp10onFinalizeEv");
    OK(vt, "bmw::PluginApp vtable present");
    OK(onError && onInit && onFinalize, "onError/onInit/onFinalize symbols present");
    if (vt && onError && onInit && onFinalize) {
        /* vt points at the vtable symbol; functions start after the 2 RTTI header words,
         * so slot N lives at vt[2 + N]. */
        OK(vt[2 + 21] == onError, "slot 21 == onError");
        OK(vt[2 + 22] == onInit, "slot 22 == onInit");
        OK(vt[2 + 23] == onFinalize, "slot 23 == onFinalize");
    }
    OK(dlsym(RTLD_DEFAULT, "_ZTVN3bmw8RunnableE"), "bmw::Runnable vtable present");

    /* 3. plugin */
    if (plugin) {
        printf("[3] plugin %s\n", plugin);
        void *lib = dlopen(plugin, RTLD_NOW | RTLD_LOCAL);
        if (!lib) {
            printf("  [FAIL] dlopen: %s\n", dlerror());
            fails++;
        } else {
            printf("  [ok]   loaded (all undefined symbols resolved against the firmware)\n");
            const unsigned char *info = (const unsigned char *)dlsym(lib, "pluginAppInfo");
            OK(info, "exports pluginAppInfo");
            if (info) {
                uint16_t major, minor;
                uint32_t rhmi;
                const char *name;
                void *create, *destroy;
                memcpy(&major, info + 0x0, 2);
                memcpy(&minor, info + 0x2, 2);
                memcpy(&name, info + 0x4, 4);
                memcpy(&rhmi, info + 0xc, 4);
                memcpy(&create, info + 0x10, 4);
                memcpy(&destroy, info + 0x14, 4);
                printf("         versionMajor=%u versionMinor=%u rhmiInterfaceVersion=%u\n", major, minor, rhmi);
                printf("         name=\"%s\"  create=%p destroy=%p\n", name ? name : "(null)", create, destroy);
                OK(sizeof(void *) == 4, "32-bit ABI");
                OK(major == 1 && minor == 0, "versionMajor/minor == 1.0");
                OK(rhmi == 1, "rhmiInterfaceVersion == 1");
                OK(create && destroy, "create/destroy non-null");
                OK(name && name[0], "name readable");
            }
        }
    } else {
        printf("[3] (no plugin given - firmware invariants only)\n");
    }

    printf("RESULT: %s\n", fails == 0 ? "PASS" : "FAIL");
    return fails == 0 ? 0 : 1;
}
