# HelloPlugin

A minimal native iDrive **PluginApp** for a rooted BMW **EntryEVO (ID5/ID6)** head unit — the hello-world
skeleton from [`../NOTES.md`](../NOTES.md) §8. It loads directly into the `HmiMain3D` UI process using the same
framework as BMW's own `SecurityMenu` / `ActiveSeating` plugins.

Derived from [EntryNav2-Android-Auto](https://github.com/Jiraiya43/EntryNav2-Android-Auto) (Jiraiya43), so this
code carries **PolyForm Noncommercial 1.0.0** and stays non-commercial.

## What it does

- Adds a **"Hello World"** entry row to the iDrive **My Vehicle** menu (`insertStateID=60`, `ST_MyV_Selection`).
- Selecting it opens a small menu with:
  - a **label whose text is set at runtime** with `updateModel(id, const char*)` — the first new framework call
    beyond what the reference plugin used;
  - a **"Change message"** button that cycles that text;
  - a **demo checkbox** stored as a file (`raBoolModel` + `updateModel(id, bool)`);
  - a **Help** child state reached through an `hmiAction`.
- A **1-second status poll** (`postRunnable`) refreshes the label (shows uptime and press count).
- A read-only **CDS logger** (`car_log.cpp`) subscribes to a list of car-data properties and writes each value to
  `cds.log` as it changes — to discover which properties this car fills and their JSON.

Everything runs **inside `HmiMain3D`**: the code is tiny, never blocks the HMI thread, and is protected by an off
switch and a crash guard (see Safety).

## Layout

| File | What |
|---|---|
| `hello_app.cpp` | the app: `create`/`onInit`/handlers/poll and the `pluginAppInfo` entry point |
| `bmw_framework.{hpp,cpp}` | stand-ins for BMW's framework and the vtable/Runnable glue (ABI only, no BMW headers) |
| `hello_ids.hpp` | the XML ids the code uses |
| `app_log.{hpp,cpp}` | bounded, maintenance-gated log writer |
| `app_guards.{hpp,cpp}` | off switch, crash guard, the file-backed demo setting |
| `car_log.{hpp,cpp}` | the read-only CDS logger |
| `HelloPlugin.manifest` | tells `HmiMain3D` what to load |
| `HelloPlugin.xml` | the UI: entry row, menu, states, components |
| `make_db.py` | builds the text and image zips (icon/preview PNGs generated here) |
| `Makefile` | builds `libHelloPlugin.so` against the car's libraries |
| `package.py` | builds the install tar with `MD5SUMS` |
| `INSTALL.md` | install / uninstall steps |

## Build & test (no car needed)

Build the toolchain image once (car-matched GCC 4.7 armhf + qemu), then build and load-test:

```sh
docker build --platform linux/amd64 -t entrynav-tc ../../hmitest     # once
../../hmitest/build-plugin.sh . make                                 # -> libHelloPlugin.so
../../hmitest/test-plugin.sh ./libHelloPlugin.so                     # RESULT: PASS
```

`test-plugin.sh` dlopens the `.so` against the car's real libraries under QEMU and checks every symbol resolves,
that `pluginAppInfo` is well-formed, and that this firmware's `PluginApp` vtable still has the expected slots. It
does **not** run `create()` — behaviour and rendering still need the car.

Then build the install archive:

```sh
python3 -I make_db.py .            # the text/image zips
python3 -I package.py              # -> artifacts/helloplugin-armhf.tar
```

## Safety

- A crash or stall here kills the iDrive UI (systemd watchdog ~75 s). Keep handlers cheap and non-blocking.
- **Recovery:** `ssh root@169.254.1.0`, then either create the off switch or remove the plugin, and reboot:
  - `touch /var/local/data/HelloPlugin/app.disable` (keeps it off), or
  - `mount -o remount,rw / && rm -rf /opt/hmi/data/ro/Plugins/HelloPlugin && mount -o remount,ro /`
- The crash guard turns the plugin off by itself after 3 short HMI runs; remove `app-guard` to re-enable.

See [`INSTALL.md`](./INSTALL.md) for the full procedure.
