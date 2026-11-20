# EntryNav2 iDrive plugin: notes

Goal: write my own iDrive plugin for a rooted BMW EntryNav2 (EntryEVO) head unit, using the
EntryNav2-Android-Auto repo as the reference. Later, read car data and talk to other modules.

- Reference repo: `~/Documents/EntryNav2-Android-Auto` (Jiraiya43/EntryNav2-Android-Auto, v0.12.x / 0.13.0-rc).
  Docs are mostly in French; `README.md` has an English version. Licence: PolyForm Noncommercial 1.0.0.
- Earlier session (started in the repo folder): `8975d531-97b6-4346-9970-99775095850c`.

## Status (2026-11-20)

| Item | State |
|---|---|
| Understand the repo: what it installs, how plugins load | done (below) |
| Survey the car (`survey.sh`) | done: `hu-survey-20261120-012145.txt` |
| Dump the car's system (`dump.sh`) | done: 2.15 GB, 51,694 entries (car and tar match), no errors |
| Check the plugin framework against my firmware | done: vtable slots and constructor match the repo |
| Map car data (CDS) and links to other modules | done, from the dump only (nothing tried on the car) |
| Hello-world plugin skeleton | **next**, planned below |
| CDS logger (which properties my car fills, and their JSON) | next, part of the skeleton |
| Decode native menu texts (`text.db`) | done: `textdb.py` reads all 38 language tables (read-only) |
| HMI caching that could hide a `text.db` edit | done from the dump; confirm on the car (section 5) |
| `text.db` writer (rename native menu rows) | not started: needs an NRV2D compressor + `set` command |
| Disassemble HmiMain3D | in progress: `hmidis.py` built; Media selection state = 20 confirmed (section 9) |
| Run HmiMain3D with video output under emulation | **not feasible** (section 9); reason recorded |
| Emulated plugin load/ABI test before shipping | done: `hmitest/`, reference plugin passes (section 9) |
| SOME/IP discovery listener, `vmostctl list-fblock`, DLT logs | later |

## Files in `~/EntryNav`

| File | What |
|---|---|
| `NOTES.md` | this file |
| `survey.sh` | read-only survey of the car over SSH. Usage: `./survey.sh [root@<ip>]` |
| `hu-survey-20261120-012145.txt` | the survey output |
| `dump.sh` | read-only dump of the car's system (details under "Dumping") |
| `dump/hu-rootfs-202402191339.tar` | the dump. **Private:** BMW firmware plus `/etc/shadow`; never put it in git |
| `dump/hu-dump-20261120-012825.txt` | dump record: counts, sha256, what was skipped |
| `dump/hurootfs.sparseimage` | case-sensitive disk image holding the extracted copy |
| `elfvt.py` | ARM ELF helper. `python3 -I elfvt.py <lib> <vtable symbol>` resolves vtable slots; `--sym <regex>` lists exports |
| `cds-properties.txt` | the 244 CDS property names the unit knows |
| `someip-services.txt` | the 23 SOME/IP services in `libSomeIPGen-apn.so.0` |
| `textdb.py` | reads `text.db`: `list`, `grep <regex> [chunk]`, `id <textId>`, `dump <chunk> <out.txt>`. Run with `python3 -I` |
| `hmidis.py` | disassembler/analyser for HmiMain3D (symbolised via `.dynsym`): `sym`, `dis`, `win`, `str`, `xref`, `callers`, `deref`. Needs `capstone`+`pyelftools` |
| `hmitest/` | emulated plugin build + load-test: `Dockerfile`, `fetch_toolchain.py`, `plugin_load_check.c`, `test-plugin.sh`, `build-plugin.sh` (section 9) |

The extracted copy is at `/Volumes/hurootfs/rootfs-202402191339`; `/Volumes/hurootfs/rootfs` and
`~/entrynav2/rootfs` (the repo's default path) link to it. After a Mac reboot, run
`hdiutil attach ~/EntryNav/dump/hurootfs.sparseimage`.

---

## 1. My head unit

- **Firmware:** `202402191339`. Build string: `EntryEvo_ID5_2403_Release-ID5_2403-525-2403A-Build-1`
  (`/opt/hmi/data/ro/version.txt`).
  - The repo's reference car runs `202111011321`.
  - The repo's compatibility list already has `202402191339` working on a G21, F20, F30, F45 and MINI F54.
- **System:** ARMv7 hard-float, Linux 3.12.25, glibc 2.15, BusyBox, systemd. The hostname is
  `xse-j6-apn-entryevo` (TI Jacinto 6 SoC).
- **Access:** an ENET cable (OBD to Ethernet), then `ssh root@169.254.1.0`.
- **Partitions:**

  | Mount | Device | Notes |
  |---|---|---|
  | `/` | `mmcblk0p3`, ext4, **ro** | 6.3 GB, 90% used, about 600 MB free. Remount rw only to install. |
  | `/var/local` | `mmcblk0p2`, ext4, rw, **noexec** | data only: settings, logs, phone and contact data |
  | `/opt/navd` | `mmcblk0p7`, 51 GB | maps (15 GB used) |
  | `/opt/app/cisu` | `mmcblk0p6`, small, rw | unknown |
  | `/tmp`, `/run`, `/var/lib`, … | tmpfs | RAM, cleared at boot |

  - To write: `mount -o remount,rw /`, then `mount -o remount,ro /` (a reboot also restores ro).
  - **Code must live on `/`.** `dlopen` and exec fail from `/var/local`.
- **Big folders:**
  - `/opt/hmi` 1.8 GB (`data` 1.7 GB, `bin` 68 MB, `lib` 24 MB)
  - `/opt/app` 113 MB
  - `/opt/navi` 440 MB, `/opt/iba` 720 MB (owner's manual), `/opt/isp` 1.9 GB
- **Tools on the unit:**
  - Present: BusyBox (152 applets), `nc`, `curl`, `wget`, `sshd` (socket-activated), `systemctl`, `journalctl`,
    `dlt-receive`, `dlt-daemon`, `LayerManagerControl`, `vmostctl`, `lighttpd` (browser).
  - **Missing:** python, gdb, strace, tcpdump. Bring static ARM builds if needed.

### HmiMain3D (the iDrive UI process)

- Unit file `/etc/systemd/system/HmiMain3D.service`:
  `ExecStart=/opt/hmi/bin/HmiMain3D -ro=/opt/hmi/data/ro -rw=/var/local/data/HMI -ibabfroot=/opt/iba -resprof`.
  - Its environment is `LD_LIBRARY_PATH=/usr/local/lib:/opt/hmi/lib`.
  - It runs at Nice -19.
- **`WatchdogSec=75`:** if the HMI thread blocks, systemd restarts the iDrive. Never block in a plugin handler.
- **`StandardOutput=null`:** a plugin's `printf` is lost, so log to a file.
- Libraries come from `/lib`, `/usr/lib`, `/usr/local/lib` and `/opt/hmi/lib`. The framework is
  `/opt/hmi/lib/libAppFramework.A.so` + `libCoreFramework.A.so`.
- Logging goes through DLT (`libdlt`), so its loader errors should be visible there (section 5).

---

## 2. How RHMI plugins work

### What the Android Auto repo installs

`tools/package_release.py` builds a tar whose files sit at their on-car paths:

```
opt/hmi/data/ro/Plugins/EntryAad/     the iDrive plugin
  libEntryAad.so                      plugin code, loaded into HmiMain3D
  EntryAad.manifest                   tells HmiMain3D what to load
  EntryAad.xml                        UI: entry button, menu states, components
  EntryAad_ALL_Texts.zip              <lang>.txt files of "id=text" lines (hmiapp/make_db.py)
  EntryAad_ALL_Images.zip             <imageId>.png files (hmiapp/make_db.py)
opt/aa/aa-supervisor, opt/aa/entry-aad   background programs started by the plugin
```

- **Install** (`docs/INSTALLATION.md` step 3): remount rw, `mkdir -p`, `cp`, `chmod 755` the binaries, `touch` a
  marker file, `sync`, remount ro, reboot.
- **Settings and logs** go in `/var/local/data/AA`; runtime state goes in `/tmp/entry-aad-*`
  (`platform/service_contract.hpp`).
- **Uninstall:** delete the two folders and reboot.
- `/opt/hmi/data/ro/Plugins` **doesn't exist on my unit yet**; the install creates it.

### Plugin folders HmiMain3D scans (at boot only)

- **`/opt/hmi/data/ro/Plugins/`**: not gated by coding. **Use this.**
- **`/opt/hmi/data/ro/PluginsCoded/`**: gated by coding. The coding map has only two names, `ActiveSeating` and
  `SecurityMenu`. The loader logs "Skipping '…' because corresponding app is not coded".
  - Neither folder exists on my firmware, so BMW shipped no coded plugins here and coding can't unlock anything.
  - HmiMain3D still contains the rear-seat ActiveSeating screen layouts (`CHmiLT_*_RSE_ActiveSeating*`).
- **`/var/local/data/HMI/Plugins/`**: also scanned, but noexec, so it's useless for code.
- **`/opt/hmi/data/ro/hmiplugins`** (→ `/opt/app/usr/hmi/data/ro/hmiplugins`) is a different internal system:
  `Bundle`/`Plugin` XML + `libhmia4a.so` / `libhmiremoting.so`. It isn't the RHMI PluginApp kind.

### Loading steps

1. **The manifest** `<Plugins>/<Name>/<Name>.manifest` (see `hmiapp/EntryAad.manifest`):
   - `<type>App</type>`, `<autoStart>yes</autoStart>`.
   - `<file>{pluginDir}/EntryAad</file>`: the loader turns this into `libEntryAad.so`.
   - `<parameters>`: `DescFile` (the XML), `TextDBFile`, `ImageDBFile`. The loader also accepts `WidgetDBFile` and
     `AssetDBFile`.
   - A `pluginAppConnector` dependency of type `Etch`, id `210`, with `asyncCallbacks yes`. Not explained
     anywhere, so copy it as is.
2. **The entry point:** `ManagedPluginApp::init` calls `dlopen`, then `dlsym("pluginAppInfo")`. That is the only
   exported symbol (build with `-fvisibility=hidden`). It is defined in `hmiapp/entry_aa_app.cpp:427-439`:
   ```cpp
   extern "C" struct EntryPluginAppInfo {
       uint16_t versionMajor, versionMinor;   // 1, 0
       const char* name; const char* vendor;
       uint32_t rhmiInterfaceVersion;         // 1
       bmw::PluginApp* (*create)(bmw::IDispatcher&, const char*, const bmw::Bundle&, const bmw::Bundle&); // +0x10
       void (*destroy)(void*);                                                                            // +0x14
   };
   ```
3. **`create()`** builds the app object without BMW headers (`hmiapp/bmw_framework.{hpp,cpp}`):
   - Stand-in declarations give the right mangled names, and the linker resolves them against the car's libraries.
   - It allocates 0x200 bytes and runs BMW's real `PluginApp` constructor in them.
   - It copies the vtable and patches slots **21 onError, 22 onInit, 23 onFinalize**.
   - Posted tasks are `bmw::Runnable`s built from a copied `_ZTVN3bmw8RunnableE` (`makeRunnable` / `postRunnable`).
   - **Verified on my firmware** with `elfvt.py`:
     - The primary `PluginApp` vtable has 34 slots (0–33) with 21/22/23 as above.
     - `Runnable` is 5 words.
     - The constructor `PluginApp(IDispatcher&, BasicString<char>, unsigned, unsigned, RHMIInterfaceVersion,
       const Bundle&, const Bundle&)` matches.
     - Not checked: the 0x200 object size (the repo says the constructor writes up to +0x174). The repo's
       `tests/test_hmiapp_load.cpp` under QEMU is the full check.
4. **`onInit`** registers handlers. Handler signature: `bool stub(void* app, const bmw::Parcel& value)`.

### Framework API (exported by `libAppFramework.A.so` on my unit)

| Call | Use | Used by AA? |
|---|---|---|
| `addHandler(actionId, delegate)` | button or checkbox pressed (`raAction`) | yes (`addAction`) |
| `addHandler(stateId, kind, delegate)` | state focus (kind 1) or visibility (kind 11) | yes (`addStateHandler`) |
| `updateModel(id, TextID / ImageID / bool)` | text id, icon or checkbox | yes |
| **`updateModel(id, const char*)`**, `(id, BasicString<char / ushort>)` | **any text at runtime** | no |
| `updateModel(id, DataTableBase …)` | list contents | no |
| `updateModel(id, int / unsigned / float / Date / Time / DateTime / Image)` | other value types | no |
| `setProperty(componentId, propId, Parcel)` | e.g. property 3 = visible, 8 = waiting | yes |
| `triggerEvent(eventId [, Parcel])` | go to a state, open a popup | yes |
| `post(Runnable*, delayMs)` | timed task on the HMI thread | yes |
| `cdsAddPropertyChangedEventHandler(name, 0, delegate)` | subscribe to car data | yes |
| `cdsGetPropertyAsync`, `cdsIsPropertyAvailable`, `cdsRemovePropertyChangedEventHandler` | read once, check, unsubscribe | no |
| `cdsSetPropertyAsync` | **write** car data: avoid | no |
| `invokeSdsEvent`, `amRegisterApp`, `getCapabilities`, `invokeCommand` | speech, app manager, … | no |

### UI XML

- **Repo example:** `hmiapp/EntryAad.xml`, with its ids mirrored in `hmiapp/rhmi_ids.hpp`.
- **BMW's own examples:** `/opt/hmi/data/ro/HmiGen_{Files,Phone,TV,Gracenote,Navigation}RemoteService.xml`, the
  service-menu pages.
- **Entry row:** `<pluginApp applicationType="Custom" insertStateID="20" insertAfterFocusID="2270"
  entryButtonFocusID="32752">` puts it in the **Media** menu (state 20 is `ST_Ent_Selection`). Use a different
  `entryButtonFocusID` from EntryAad.
  - `entryButton action= model= imageModel= previewModel=`: the raAction, text, icon and side-preview state.
  - BMW's pages use `applicationType="ServiceMenu"` instead.
- **Sections:** `actions` (`raAction` handled in code, `hmiAction target=` jumps to a state, `combinedAction`),
  `models`, `events` (`focusEvent`, `popupEvent`; `raIntModel modelType="NativeStateID"` for native screens),
  `hmiStates` (child states via `parentId`, plus `toolbarHmiState`).
- **Components used by AA** (proven on the car): `button`, `checkbox`, `separator`, `label`, `image`.
- **Extra components in BMW's XML:**
  - `list` + `raListModel`
  - `gauge` + `raGaugeModel min= max= increment= value=`
  - `raDataModel` (pairs with `updateModel(id, const char*)`)
  - `formatDataModel formatString="%0 %1"`
  - `input`, `locationInput` (text entry)
  - `selectAction` and `tooltipModel` on buttons
  - `textIdModel preinst="true"`: BMW's built-in translated texts
- Both styles appear in BMW's XML: attributes (`id="3"`) and child elements (`<id>3</id>`).
- **Menu placement** (attributes on `<pluginApp>`):
  - `insertStateID`: which menu. `insertAfterFocusID`: after which row. `entryButtonFocusID`: the new row's own
    focus id. `applicationWeight` may affect ordering.
  - The loader also accepts **`replaceFocusID`**, which presumably replaces an existing row. Untested.
  - The top-level menus are `ST_Nav_Selection`, `ST_Ent_Selection` (Media), `ST_Com_Selection`, `ST_MyV_Selection`
    (My Vehicle) and `ST_CDr_Selection` (ConnectedDrive).
  - **Only Media is confirmed:** state 20, after focus id 2270 (the AA repo found it by disassembly). The other
    states' numbers and row focus ids are compiled into HmiMain3D and need disassembly or careful testing.
  - `.pba` files in `/opt/hmi/data/ro/app/*/` are layout templates (`LT_State_Selection`, `LT_Button_1Row_…`), not
    state-id tables.
- **Full XML vocabulary** the loader knows (strings in HmiMain3D):
  - Layout attributes: `columnCount`, `elementWidth`, `elementHeight`, `elementSpacingX/Y`, `alignmentX/Y`,
    `offsetX/Y`, `layoutGroup(s)`, `modal`, `weight`.
  - Entry row and preview: `previewText(Id)`, `previewImageId`, `previewState`, `quickAccessible`,
    `quickAccessImageId`, `mainMenuEntryButton`, `padMenuEntry`.
  - Models: `raIntModel`, `raBoolModel`, `raGaugeModel`, `raChartModel` (`xAxisMin/Max`, `yAxisMin/Max`),
    `raListModel`, `raDataModel`, `raImageModel`, `raRollModel`, `formatDataModel`, `textIdModel`,
    `imageIdModel`, `sidDataModel`, `dateModel`.
  - Actions: `raAction`, `hmiAction`, `linkAction`, `combinedAction`, `selectAction`, `changeAction`,
    `suggestAction`, `resultAction`, `inputAction`.
  - Events: `focusEvent`, `popupEvent`, `modalPopupEvent`, `notificationEvent`, `statusbarEvent`.
  - States: `hmiState`, `toolbarHmiState`, `audioHmiState`, `popupHmiState`.
- **Component properties** used by the AA app: 3 = visible, 8 = waiting (spinner). On images: 2 (false), 9/10 =
  549/484 (presumably width and height), 20/21 = 0 (presumably x/y offset). Other numbers are unknown.
- **Texts zip:** one `<lang>.txt` per language, `id=text` lines plus `100000=<language name>`, ASCII only.
- **Images zip:** `<imageId>.png`. AA uses 55001+, so use another range.

### Rules

- The .so runs **inside HmiMain3D**, so a crash or a stall kills the iDrive UI (watchdog 75 s).
  - Keep plugin code tiny. Put heavy work in a separate program on `/` (e.g. `/opt/<name>/`), started with
    `posix_spawn` (as `hmiapp/service_link.cpp:142` does).
  - Keep a crash guard (`hmiapp/app_guards.cpp`): one line per load goes into a file, which is deleted after
    2 minutes of uptime; at 3 lines `create()` returns `nullptr`. Also keep an off-switch file.
- **Recovery:** SSH in, delete the plugin folder or create its disable file, then reboot. As a last resort, hold
  the iDrive power button for about 30 s.
- **Before installing a .so,** check it on the car without running it:
  ```sh
  L=/usr/local/lib:/opt/hmi/lib:/usr/lib:/lib
  LD_TRACE_LOADED_OBJECTS=1 LD_WARN=yes LD_BIND_NOW=yes LD_LIBRARY_PATH=$L /lib/ld-linux-armhf.so.3 ./libX.so \
      2>&1 | grep -E 'not found|undefined symbol|not defined in file'    # must print nothing
  ```
- **Loader errors** (strings in HmiMain3D) to look for in DLT:
  - `Plugins directory '…' not found`, `Loading of plugin failed:`
  - `Error: Loading manifest XML failed (`, `Error: Manifest does not contain a <plugin> tag`
  - `Error: Plugin has no name`, `Error: Plugin does not refer to a UI description file`
  - `Error: Plugin has no code behind dynamic link library`, `Error: Plugin is not allowed`
  - `Error: Plugin has no valid PluginAppConnector`, `Error: Unable to load dynamic link library:`
  - `Error: Plugin does not contain a pluginAppInfo entry point`,
    `Error: The plugin's pluginAppInfo entry point is invalid`, `Error: Plugin already running`
- **Licence:** reusing `bmw_framework.cpp` etc. means my plugin carries PolyForm Noncommercial and stays
  non-commercial.

---

## 3. Car data

- **Easy path: CDS (Car Data Service), from inside the plugin.**
  - The calls are in the API table above. The repo subscribes to `driving.gear`, `sensors.PDCStatus`,
    `hmi.graphicalContext`, `communication.callStatus0/1`, `vehicle.dayNightChangeOver` and
    `driving.mode`/`mode35up` (`hmiapp/car_signals.cpp`).
  - Values arrive as UTF-16 JSON strings, e.g. `{"PDCStatus":1}`. Parse them with the repo's `narrow()` +
    `hmiapp/cds_parse.hpp`.
  - **244 property names** (from `libhmiremoting.so`) are in `cds-properties.txt`, grouped as: climate 22,
    communication 21, controls 18, driving 41, engine 8, entertainment 56, hmi 9, navigation 31, sensors 21,
    vehicle 17. Highlights:
    - **driving:** `speedActual`, `speedDisplayed`, `acceleration`, `acceleratorPedal`, `brakeContact`,
      `steeringWheel`, `odometer`, `averageConsumption`, `averageSpeed`, `gear`, `parkingBrake`,
      `sliActualSpeedLimitInfo`, `laneBoundaries`
    - **engine:** `RPMSpeed`, `temperature`, `torque`, `consumption`, `rangeCalc`, `status`
    - **sensors:** `fuel`, `battery`, `batteryTemp`, `temperatureExterior`, `temperatureInterior`, `doors`, `trunk`,
      `lid`, `seatbelt`, `seatOccupied*`, `tirePressureWarning`, `PDCRangeFront`/`Rear`, `SOCBatteryHybrid`
    - **vehicle:** `VIN`, `type`, `units`, `time`, `language`, `country`
  - **Unknown:** which properties my car fills, and the exact JSON of each. The CDS logger is meant to find out.
    The open-source AAIdrive project uses the same names (as far as I recall) and is a reference for the formats.
  - Handlers run on the HMI thread, so keep them cheap.
- **GPS:** the repo reads the car's GPS passively (`platform/evo_gps`).
- **No raw CAN** (section 4).

---

## 4. Links to other control modules

All of this comes from the dump; nothing has been tried on the car.

- **CAN is never visible as frames.** The dump has no CAN kernel modules and no `can0`/SocketCAN references. The CAN
  buses end at the central gateway (BDC/ZGW) and at the unit's vehicle-side chip.
- **Ethernet + SOME/IP:**
  - `eth0` (ks8851) is bridged as `vbr0`, with VLANs created by `etc/udev/scripts/netconfig` (also
    `usr/local/bin/net-init.sh`).
  - The roles below are my guesses from the subnets, traffic shaping and peers:

    | Interface | Unit address | Shaped | Likely role |
    |---|---|---|---|
    | `vbr0.73` | 160.48.199.119/25 | 24 Mbit | main vehicle network: cluster at **160.48.199.96**, SOME/IP |
    | `vbr0.77` | 160.48.199.225/29 + IPv6 | 2 Mbit | telematics (ATM) at .226: `datacomipd`, `telematicsassistd` |
    | `vbr0.80` | 160.48.199.185/29 | 1 Mbit | second ATM link at .186 |
    | `vbr0:1` | 192.168.11.11/24 | none | unknown |

  - Service discovery is `sd-daemon` (`SomeIP-SD.service`). Bindings are CommonAPI-SomeIP
    (`etc/CommonAPI/CommonAPI.conf`); the generated interfaces are in `usr/local/lib/libSomeIPGen-apn.so.0`.
  - **23 services** are listed in `someip-services.txt`:
    - INFOTAINMENT: KombiInterface (+_2), REMOTEINSTRUMENTCLUSTER (DisplaySink, RICServiceGuidance, RICServiceList),
      SatellitePositioning, ControllerElements, ConsumptionHistory, Telephone, WLANAccessPoint, NFC.NfcMaster,
      DataCommunication, EgoModelUpload, REMOTESERVICES, AshellMsgHandler
    - BODY: ComfortFunction, SmartAccess
    - ENVIRONMENTALMODEL: LaneBoundaries, RoadProperties, SignRecognitionFrontCamera
    - DASS: StatusRCP, XView3D
    - INFRASTRUCTURE.TESTABILITY: EnhancedTestabilityServiceHigh. `SomeIP-SD.path` starts `ET_Service.target`
      when `/tmp/some-ip/et` exists.
  - Module names referenced: ZGW, BDC, Kombi, Kombi2, ATM, KAFAS, iCAM2, iCAM2StatusRCP, CID, NBTEvo.
  - **The repo already talks SOME/IP:** `platform/kombi_client.cpp` / `kombi_someip.cpp` send hand-built SOME/IP
    over plain UDP to the cluster, service `0xB006` (`BMW.IC.Guidance`), for turn arrows on the cluster and HUD.
- **vMOST:**
  - `vmostd` routes MOST-style FBlock messages over an "IMC" socket (`libvmostpluginimc.so`) to the unit's
    vehicle-side chip.
  - The repo uses `libvmostclient.so.1` (dlopen) to shadow FBlocks for the iDrive controller (`evo_knob.cpp`,
    instances 01/03/05) and Wi-Fi (`evo_wlan.cpp`). The API is described in `platform/vmost_client.hpp`.
  - `vmostctl list-fblock` lists FBlocks and their owners (read-only).
  - `vmostctl` can also inject `<DeviceAddress>.<FBlockID>.<InstID>.<FunctionID>.<OPType>[.<DATA>]`, which sends
    to the car.
- **D-Bus inside the unit:** e.g. `com.bmw.navigation.guiding` (BMW navigation), `org.alps.evolution` (Bluetooth).
- **Safety:** listening is low risk (CDS subscriptions, FBlock shadows, SOME/IP events). Sending reaches real
  modules: `BODY.ComfortFunction` very likely controls windows, mirrors or seats. Stay read-only until a payload is
  understood, and test only with the car parked.

---

## 5. Hidden menus, logging and runtime leads (not tried)

- **Quick test menu:**
  - `CStbHMIControl::CEnableQuickTestMenu::setQuickTestMenuSwitch(TSvcBitfield<4>)` is a property of an
    "HMIControl" service that HmiMain3D serves (stub/proxy pair). It is set from outside: another module or a
    diagnostic tester.
  - It is tied to `CCarSelectionActivity::onNaviQuickTestMenu(bool)` and `CNaviQuicktestActivity`, which suggests
    a navigation quick-test page in the Car menu.
  - Enabling it would need HMIControl's FBlock/function id (disassemble HmiMain3D), then `vmostctl` injection.
- **Service menu:** `CCarServiceMenuActivity` / `CDevServiceMenu` host BMW's `HmiGen_*RemoteService.xml` pages
  (Bluetooth name, IMEI, signal strength, GPS…). How it is opened on this unit is unknown.
- **Runtime plugin loading:** `CAppManager::refreshPluginApps` and `CDevHMIControl::onPluginLoad` / `onPluginUnload`
  exist. If something exposes them, plugins could be tested without a reboot. Not found yet.
- **DLT logs** (should show HmiMain3D's loader errors):
  - `dlt.service` starts through `dlt.path` when `/tmp/logdata/activate_dlt` changes.
  - Its config `/etc/dlt_variant.conf` → `/var/local/data/DLT/dlt_Link.conf`, which is on the data partition and
    not dumped: read it on the car.
  - Then DLT Viewer on the Mac over ENET, probably on the default port 3490.
- **Native menu texts: `text.db` is decoded** (`~/EntryNav/textdb.py`, read-only: `list`, `grep`, `id`, `dump`).
  - Files: `/opt/hmi/data/ro/{bmw,bmwi,bmwm,mini,j29}/db/text.db`, one per brand. A BMW presumably uses `bmw/`.
  - **Header:** magic `de ca fb ad`; from 0x20, big-endian offsets of 38 index records (24 bytes: `22000001`,
    chunk offset, `deadbeef`, 0, `ffffffff`, timestamp).
  - **Chunk:** BE u32 1, BE u32 length of what follows, LE u32 uncompressed size, then **UCL NRV2D** (8-bit bit
    buffer), the same algorithm `libhmizip.so` exports.
  - **Text:** UTF-16LE with BOM, `id<TAB>text` lines, **15,696 texts per language**. `\n` inside a text is a
    literal backslash-n.
  - **No checksum found** in the records or chunk headers.
  - **Chunk → language** (guessed from sample texts): 1 de, **2 en-GB ("Tyre")**, **3 en-US ("Tire")**, 4 es,
    14 es-US or pt-BR, 5 it, 6 fr, 8 nl, 9 ar, 10 zh (traditional), 11 zh (simplified), 12 ko, 13 ja, 17 ru, 18 pl, 19 el, 20 tr, 21 hu, 23 sv, 24 pt, 27 sk, 28 cs, 29 sl, 30 da, 31 no,
    32 fi, 33 id, 34 th, 37 uk. 0 holds placeholder ids; 7/15/16/22/25/26/35/36 are `TBD_` placeholders.
  - **Tyre texts:** 8944/8945/75144 "Tyre Pressure Monitor", 13320/13322 "Tyre pressure menu", 27912 "Tyre
    pressure", 27888/27889/48056/66176/66304/70792 "Tyre settings", 87920/87922 "Tyres", plus many messages.
    Which id a given menu row uses is not known yet: change one at a time and look.
  - Native menu *structure* is compiled into HmiMain3D (generated `C…ActivityGenerated` classes) plus widget
    layouts in `assetDB` (`.pbr`/`.pbw`); rows refer to texts by id. Renaming = editing `text.db`; adding or
    removing native rows is not practical.
  - Other files: `speech.db` (voice), `_dyndata` / `hdb` (speller dictionaries).
  - **To rename a row:** decode the language chunk, replace the text, re-encode with NRV2D, append the new chunk at
    the end of the file and point its index record at it (everything else byte-for-byte unchanged). Then
    install, clear the preload cache (below) and reboot. Keep the original for recovery; a firmware update
    undoes the change.

- **HMI caching** (from strings in `libhmidb.so` and HmiMain3D; not yet confirmed on the car):
  - **Preload cache (persistent, the one that matters):** `CHmiPreloadCache`, file `resource.cache`.
    - HmiMain3D runs with `-resprof`: it records the resources loaded at start-up (`resprof.txt`, written to the
      `-rw` folder, i.e. `/var/local/data/HMI`) and keeps their **raw file contents** in `resource.cache`.
    - At boot it logs "Load resource.cache", maps the file, and serves those files "from preload cache" instead of
      "from OS" (`CHmiBaseFileResourceProvider::loadFromFile`).
    - It is **written once**: "cache file already present, do not write". It has a "verify cookie"
      (`hmi_cookie()`, contents unknown, presumably a software version), so an edited file on `/` most likely
      **keeps being served from the old cache** until the cache is removed.
    - It is size-limited ("buffer full, do not add file %s", `MaxPreloadCacheSize`), so whether the 4.9 MB
      `text.db` is inside is unknown.
    - **Control files** next to it:
      - `resource.cache.forbidden`: neither read nor write the cache. Boot is slower; good for testing.
      - `resource.cache.verify`: compare cached files with the files on disk and log "PRELOADCACHE: VERIFY
        error in file %s" or "VERIFY OK" (DLT). This shows directly whether `text.db` is cached.
    - **After editing any HMI data file:** delete `resource.cache` (rebuilt at the next start), or use
      `resource.cache.forbidden`, then reboot.
  - **RAM caches:** `CHmiStringResourceCache`, `CHmiSimpleResourceCache` and the glyph and bitmap caches. A reboot
    clears them.
  - **RHMI folders** (`-rw` folder): an RHMI cache folder (size-checked at start: "Size of cache folder was ok"),
    `FbmTxtPers` (persistent texts of remote/plugin apps, `CRhmiPersistentFbmTextResourceProvider`) and
    `PersistentA4ARes` (connected-app resources). These may also hold stale **plugin** texts or images after an
    update. The AA project's upgrades show up after a reboot, so plugin resources don't seem to be served stale,
    but check these folders if a plugin text doesn't change.
  - **On-car checks (read-only):**
    ```sh
    ls -la /var/local/data/HMI/
    find /var/local -name 'resource.cache*' -o -name resprof.txt
    grep -c 'text.db' /var/local/data/HMI/resprof.txt        # was text.db loaded at start-up?
    grep -c 'db/text.db' /var/local/data/HMI/resource.cache  # is it inside the cache?
    ls -la /var/local/data/HMI/FbmTxtPers /var/local/data/HMI/PersistentA4ARes
    ```
  - `assetDB/resources.ptr`: a text protobuf mapping widget names to `numericId`s.
  - `icudt54l.dat`: ICU.

---

## 6. Build toolchain

- **Image:** `docker build -t entrynav2-tc:4.7 toolchain`, in the repo. It's Ubuntu 12.10 with GCC 4.7 armhf.
  On Apple Silicon it runs under emulation: slow, but it works.
- **Running it:** `bash toolchain/tc.sh <cmd>` mounts the repo on `/work` and the rootfs on `/sysroot` (read-only).
  - Pass the real path: `HU_ROOTFS=/Volumes/hurootfs/rootfs-202402191339`. Docker's handling of symlinked bind
    mounts on macOS isn't reliable.
  - To build outside the repo, copy the one-line `docker run` from `toolchain/tc.sh`.
- **Plugin build flags** (`Makefile:86-97`):
  - Compile: `-std=gnu++0x -O2 -march=armv7-a -mfpu=neon -mfloat-abi=hard -fPIC -fvisibility=hidden
    -fvisibility-inlines-hidden`.
  - Link: `-shared -Wl,--allow-shlib-undefined -L$SYSROOT/{usr/lib,lib,usr/local/lib,opt/hmi/lib}` plus
    `-Wl,-rpath-link,…`, then `-l:libAppFramework.A.so -l:libCoreFramework.A.so -lpthread -ldl`.
- **QEMU tests** need `qemu-arm` (qemu-user), which is Linux only, so use a Linux container or VM:
  `qemu-arm -L <rootfs> -E LD_LIBRARY_PATH=/opt/hmi/lib:/usr/local/lib:/usr/lib:/lib -E LD_BIND_NOW=1 <program>`.
- **macOS scripts** run under `/bin/bash` 3.2. It can't parse `case` inside `$(cat <<EOF …)`, so use
  `read -r -d '' VAR <<'EOF'`, and check with `/bin/bash -n`, not Homebrew's bash.

---

## 7. Dumping the car's system (done; repeat after a firmware update)

1. **Survey:** `./survey.sh [root@<ip>]`. Read-only. It writes `hu-survey-<date>.txt` and a summary (dump size,
   the library folders HmiMain3D uses, folders the dump would miss).
2. **Dump:** `./dump.sh [root@<ip>] [--libs-only] [--no-extract] [-y]`. Read-only on the car; one password prompt.
   - **What it copies:** `bin sbin lib usr etc opt/hmi opt/app` (about 2.1 GB). `--libs-only` copies about 0.5 GB,
     without `opt/hmi/data`.
   - **What it skips:** partitions mounted inside those folders (`/opt/app/cisu`, `/etc/machine-id`). It never
     copies `/opt/navd`, `/opt/navi`, `/opt/iba`, `/opt/isp` or `/var/local`.
   - **On the Mac:** it streams the tar to `dump/`, checks the entry count, writes a record with sha256, extracts
     into `dump/hurootfs.sparseimage` (case-sensitive APFS, mounted on `/Volumes/hurootfs`), makes absolute
     symlinks relative (352 on my unit), and links `/Volumes/hurootfs/rootfs` and `~/entrynav2/rootfs`.
   - `/opt/app` is needed because `/usr/local/lib` has symlinks into `/opt/app/usr/...` (browser libs, and the alps
     Bluetooth stack in `/opt/app/usr/BTMedia`).
3. **Manual equivalent:**
   `ssh root@169.254.1.0 'cd / && tar -cf - bin sbin lib usr etc opt/hmi opt/app' > hu-rootfs.tar`
   - This picks up `/opt/app/cisu` too; `dump.sh` leaves it out.
   - Extract onto a case-sensitive volume (`hdiutil create -fs 'Case-sensitive APFS' …`).

---

## 8. Next steps

### Hello-world plugin + CDS logger (next)

Self-contained, so it can move to its own repo later.

- **Naming:**
  - Plugin: `HelloPlugin` → `/opt/hmi/data/ro/Plugins/HelloPlugin/libHelloPlugin.so` + `.manifest`, `.xml` and the
    two zips.
  - Data: `/var/local/data/HelloPlugin`.
- **Ids:** its own `pluginAppInfo` name and vendor, a different `entryButtonFocusID`, and a different image-id range.
- **Code:**
  - A copy of `bmw_framework.{hpp,cpp}` in its own namespace, keeping the licence header.
  - A bounded log file (stdout goes to /dev/null).
  - A crash guard and off switch.
  - `create` / `destroy` / `onInit`. Nothing blocking on the HMI thread.
- **UI** (start from proven AA components, then add one new one at a time):
  - An entry row in Media that opens a menu.
  - **A label driven by `updateModel(id, const char*)`** (free text, the first new thing to try).
  - A button that changes the label.
  - A checkbox stored as a file (`raBoolModel` + `updateModel(bool)`).
  - A Help child state through an `hmiAction`.
  - A 1 s status poll through `postRunnable`.
- **CDS logger:** subscribe to a list of properties from `cds-properties.txt` and log each value as it changes. It
  shows which ones my car fills, and their JSON.
- **Assets:** a script that builds the text and image zips (with a generated icon and preview PNG) and the install
  tar with `MD5SUMS`.
- **Build and test:** a Makefile run through `tc.sh`, and a QEMU load test adapted from `tests/test_hmiapp_load.cpp`.
- **Docs:** install and uninstall steps, like the AA install with the folder names changed.

### Later

- `text.db` writer: an NRV2D compressor and `textdb.py set <id> <text> --chunks 2,3 --out <file>`. It needs a
  dry run that lists what changes, a round-trip check (decode the result and diff it against the original), and
  must leave untouched chunks byte-identical. Then run the on-car cache checks above before the first install.
- Try `raDataModel`, `list` and `gauge` from BMW's XML, one at a time.
- On the car (read-only): `vmostctl list-fblock`; `cat /var/local/data/DLT/dlt_Link.conf`; enable DLT and watch
  the HMI logs with DLT Viewer.
- A receive-only SOME/IP discovery listener on `vbr0.73` (a tiny static ARM program) to map live services, then
  method and event ids from `libSomeIPGen-apn.so.0`.
- A helper program under `/opt/<name>/` for anything heavy (network, polling), started with `posix_spawn`.

### Open questions

- What the `Etch` connector id `210` means, and whether a second plugin can share it.
- Whether `entryButtonFocusID` and image ids must be unique across plugins.
- What triggers "Error: Plugin is not allowed".
- Which CDS properties are populated on my car, and their formats.
- The VLAN roles, and what sits on `192.168.11.0/24`.
- How to reach the service menu, the quick test menu, and runtime plugin load/unload.
- Whether `text.db` is in `resource.cache`, and what the preload cache's verify cookie contains.
- Which text id each native menu row uses (e.g. "Tyre Pressure Monitor": 8944, 8945 or 75144).
- Whether any other check (beyond the absent checksums) rejects a modified `text.db`.

---

## Useful files in the repo

- `hmiapp/entry_aa_app.cpp`: the plugin (create, onInit, handlers, status poll, `pluginAppInfo`).
- `hmiapp/bmw_framework.{hpp,cpp}`: BMW framework stand-ins and vtable patching.
- `hmiapp/EntryAad.xml`, `hmiapp/rhmi_ids.hpp`, `hmiapp/EntryAad.manifest`, `hmiapp/make_db.py`.
- `hmiapp/app_guards.cpp`, `app_log.cpp`, `service_link.cpp`, `car_signals.cpp`, `cds_parse.hpp`.
- `platform/kombi_client.cpp`, `kombi_someip.cpp` (SOME/IP to the cluster); `vmost_client.hpp`, `evo_knob.cpp`,
  `evo_wlan.cpp` (vMOST); `evo_gps` (GPS); `service_contract.hpp` (paths).
- `tests/test_hmiapp_load.cpp`, `tests/run_qemu.py`, `tools/package_release.py`, `Makefile`, `toolchain/`.
- `docs/ARCHITECTURE.md`, `docs/INSTALLATION.md`, `docs/MAINTENANCE.md`, `docs/COMPATIBILITE.md` (French).

---

## 9. Disassembly, emulation and the plugin test harness (2026-11-20)

### Disassembling HmiMain3D

- **HmiMain3D is `.symtab`-stripped but keeps ~318k defined C++ symbols in `.dynsym`** (266k FUNC, 52k
  OBJECT/vtables) with a 30 MB `.dynstr`. So it is effectively symbolised: any address resolves to a name.
  Non-PIE `ET_EXEC`, all Thumb-2, `.text` ≈ 20 MB at `0x2490bd0`, `.rodata` 6.3 MB. A function symbol's low bit
  is the Thumb bit (real entry `value & ~1`); vtable slots hold absolute pointers (readable straight from the file).
- **`hmidis.py`** drives this (needs `capstone`+`pyelftools`; e.g. a venv): `sym <regex>`, `dis <name|0xaddr>`,
  `win <0xaddr>`, `str <regex>`, `xref <0xaddr>` (LE-word refs across the image), `callers <name|0xaddr>` (who
  calls X, ~20 s sweep of all functions), `deref <0xaddr>`.
- **Confirmed: Media / `ST_Ent_Selection` = state 20.** `CEntSelectionActivity::onInitialize(int)` asserts
  `stateID == 0x14`. Matches the AA repo's value → validates the toolchain against ground truth.
  - The top menus are served by `CHmi{Car,CDr,Communication,Ent}Application` + `CNaviSelectionMenuProvider`
    (`initMenus`/`initMenuProviders`). The selection-state id is **not** inline there — it comes from a virtual
    getter chain; extracting Nav/Com/MyV/CDr still needs a careful trace (don't trust the app-type enum for this).
  - Separate `eHmiApplicationType` enum (from `getType()` = `[app+8]`, set in each app ctor's call to
    `CHmiApplicationAbstract::C2`): **Ent=1, Com=2, Nav=3, CDr=4, Car=6.** This is the app type, NOT the HMI
    state id — don't confuse the two.

### Running HmiMain3D for video: not feasible under emulation

Tried and ruled out (don't retry without new hardware/components):

- **GPU is hardware-locked.** `libEGL`/`libGLESv2`/`libpvr_wlegl` are the TI OMAP5 **SGX PowerVR** binary blobs
  (`omap5-sgx-ddk-um`, "eurasia", PVRSRV). They need the `pvrsrvkm` kernel driver + the real GPU; no software
  fallback. EGL init can't succeed in QEMU.
- **The compositor isn't in the dump.** HmiMain3D is a Wayland / GENIVI-IVI client (`libilm{Client,Common,Control}`);
  no weston/LayerManager binary, libweston or ivi-shell was dumped (lives outside the dumped paths).
- **Empirically:** under `qemu-arm-static -L <rootfs>` the full library closure resolves (dump is complete), but
  HmiMain3D segfaults in early static init (≈2,900 ctors expecting DLT/D-Bus/persistence/SOME/IP services).
- **Corroboration:** the AA repo's own QEMU harness sets `visual_result = "NOT TESTED"` and stubs the compositor
  (`tests/lm_cli_stub.c`). Nobody renders this in emulation.
- Pixels would require porting armhf Mesa (llvmpipe) over the PVR blobs + building a Weston/ivi-shell compositor +
  stubbing the whole BMW service mesh — multi-day, low odds. Not pursued.

### What IS done: emulated plugin load/ABI test (`hmitest/`)

The real pre-ship risk is an ABI/load mismatch, which QEMU *can* catch. Working and proven.

- **Toolchain.** The repo's `FROM ubuntu:12.10` image no longer builds (modern Docker rejects its v1 manifest).
  `hmitest/Dockerfile` + `fetch_toolchain.py` rebuild the **same** toolchain on `debian:bookworm-slim`: they pull
  the quantal (12.10) cross `.debs` from `old-releases.ubuntu.com` and `dpkg -x` them (no debootstrap/apt-in-chroot,
  which both fought the ancient distro). Result: **GCC 4.7.2 armhf, eglibc 2.15, libstdc++ 6.0.17 (GLIBCXX_3.4.17)**
  — an exact match to the car (`crosstool-NG Linaro 4.7.3 2013.03`). Build once:
  `docker build --platform linux/amd64 -t entrynav-tc hmitest` (≈200 MB image; must be `linux/amd64` — the amd64
  GCC runs under emulation on Apple Silicon).
- **Harness** `plugin_load_check.c` (prebuilt into the image) does what `ManagedPluginApp::init` does minus
  `create()`: dlopen `libAppFramework.A.so` (RTLD_NOW → surfaces unresolved framework symbols); verify this
  firmware's `bmw::PluginApp` vtable has onError/onInit/onFinalize at **slots 21/22/23** and the `Runnable` vtable
  exists; then dlopen the plugin (RTLD_NOW → surfaces the plugin's undefined symbols against the real firmware) and
  check `pluginAppInfo` (version 1.0, rhmi 1, non-null create/destroy, readable name).
- **Run:** `hmitest/test-plugin.sh <plugin.so>` (set `HU_ROOTFS` if the rootfs isn't at the default
  `/Volumes/hurootfs/rootfs-202402191339`). It runs the harness under `qemu-arm-static -L /sysroot`.
  - The repo's reference `libEntryAad.so` (built with `build-plugin.sh ~/Documents/EntryNav2-Android-Auto make
    hmiapp CXX=arm-linux-gnueabihf-g++-4.7`) → **RESULT: PASS**.
  - Negative tests pass too: a `.so` with no `pluginAppInfo`, and one with an undefined `bmw::` symbol, both **FAIL**
    (the latter at dlopen, naming the symbol). So a green PASS is meaningful.
- **Build plugins** with `hmitest/build-plugin.sh <work-dir> <command…>` (the `toolchain/tc.sh` equivalent on a base
  that still builds; `CXX=arm-linux-gnueabihf-g++-4.7`, `SYSROOT=/sysroot`).
- **Caveat:** this checks load/ABI, not behaviour — `create()`/`onInit()` and any rendering still need the car.
