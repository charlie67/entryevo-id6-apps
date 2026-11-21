# Ambient lighting and the LED ring: how the head unit drives them

Findings from the dump (firmware `202402191339`), worked out on 2026-11-20 by disassembling
`/opt/hmi/bin/HmiMain3D` and `/opt/hmi/lib/libhmil6services.so` with `hmidis.py`.
**Nothing here has been tried on the car.**

Tools: `hmidis.py` needs `capstone` + `pyelftools` (e.g. `python3 -m venv venv && venv/bin/pip install capstone pyelftools`,
then `venv/bin/python3 -I hmidis.py <elf> <cmd> ...`). Menu texts came from `textdb.py` (`mini/db/text.db`, chunk 2 = English).

## Summary

- The head unit does not drive the lights itself. HmiMain3D sends messages to other modules, which own the LEDs.
- There are **two separate kinds** of message:
  1. **Effects** (volume, temperature, fan, Bluetooth…): one-off or held events sent to the LED-ring service
     (`CPxySystemFunctionZIN`, ZIN = the MINI central instrument).
  2. **Permanent colour**: settings messages sent by the lighting menu. There are three paths (section 2).
- **No RGB field exists anywhere.** The closest is a hue value, sometimes with saturation and brightness (section 3).
- Only HmiMain3D (and `libhmil6services.so`, its proxy library) uses the ZIN service. No audio or climate daemon
  talks to it directly.

---

## 1. Effects: volume and air-con animations

### Call chain

```
Volume knob / air-con change
  → HmiMain3D event handler
  → CDevCarZIN (head-unit driver for the LED-ring module, via the IDevCarZIN interface)
  → CPxySystemFunctionZIN, FBlock 0xD1 (libhmil6services.so)
  → vmostd → the module that owns the lights, which plays the effect
```

The step after vmostd (IMC link to the vehicle-side chip) is assumed from NOTES.md and not confirmed for FBlock `0xD1`.

### Air-con

`CCarZINEventServiceID4` (source `libmyvvehicleconfig/source/CCarZINEventServiceID4.cpp`) subscribes to
`CPxyClimate::CAirConditionDRStatus` / `CAirConditionPSStatus`. When the set temperature (`statusDesiredTempDR`) or
fan speed (`statusBlowerSettingDR`) changes, it calls `IDevCarZIN::startAnimation(event, false)`.

| zin event | Trigger | Log string next to the call |
|---|---|---|
| 27 (0x1b) | Driver set temperature changed | "Trigger Temperature Settings Animation Driver" |
| 28 (0x1c) | Driver fan speed changed | "Trigger Blower Animation Driver" |
| 34 (0x22) | Passenger set temperature changed | "Trigger Temperature Settings Animation Passenger" |
| 35 (0x23) | Passenger fan speed changed | "Trigger Blower Animation Passenger" |

- An event fires only when the new value differs from the cached one and isn't `0xFF`.
- A `CPrcTimer` check stops it firing at startup.

Handler addresses: `onPxyAirConditionDR` @ `0x2c06ef0`, `onPxyAirConditionPS` just before it.

### Volume

- `CHmiVolumeIndicatorService::startZINAnimation()` calls `startPermanentEvent(32 /*0x20*/, prio 0xFF)` when the
  volume popup opens.
- `stopZINAnimation()` calls `stopPermanentEvent(32)` when it closes.
- So the volume effect is **held** while the knob turns, not a one-off animation.
- Log strings: "[CHmiVolumeIndicatorService::%s] Start/Stop ZIN animation".

### Other users of the ZIN service

- Bluetooth (`CDevCarBluetooth::startZinAnimation`)
- the welcome animation
- MSA (engine auto start-stop), as permanent and temporary events
- DSC (stability control)
- gear / driving mode (`GearboxProgramDisplay`)
- convertible roof position
- distance to the next navigation turn
- terminal (ignition) status, and the always-open timer

### Wire format

| Call | Proxy message | OpType | Payload |
|---|---|---|---|
| `CDevCarZIN::startAnimation` | `CLEDRing_AnimationTriggerEvent::startResultAck(handle, EEventID)` | 6 (StartResultAck) | u16 sender handle, u8 event ID (checked ≤ `0x6b`) |
| `CDevCarZIN::startPermanentEvent` | `CLEDRing_SemiPermanentEvent::startResultAck(handle, EEventID, prio, bool)` | 6 | handle, event, prio, flag |

- **Proxy:** `CPxySystemFunctionZIN` constructor (`0x49a28c` in libhmil6services) passes FBlock **`0xD1`** to the
  base class.
- **Event mapping:** `CDevCarZIN::mapToMOST` (`0x2c02310`) is a 46-entry table. It is the identity for events 0–36.
  37 → `0x31`, and 38–45 → `0x64`–`0x6b`.
- **Vtable:** `CDevCarZIN` vtable `_ZTV10CDevCarZIN` @ `0x3a76fc8`. Through the `IDevCarZIN` sub-object
  (`_ZThn24_` thunks), slot `+0x24` = `startAnimation`, `+0x28` = `startPermanentEvent`,
  `+0x2c` = `stopPermanentEvent`. All calls go through the vtable, so there are no direct callers to find.
- **Not found:** the function ID for each call. The constructor registers them indirectly.
  `vmostctl list-fblock` or a DLT trace on the car should show them.

### What gates an effect

Before sending, `startAnimation` / `startPermanentEvent` check:

- `isEventGroupEnabled(event)`: the user's LED-ring settings (`CLEDRing_Settings`: LED-ring switch, animation
  switch, animation-display bitfield). The settings screen is `CCarDisplaysIkoneRingActivity`.
- `isEventAllowedInPowerMode(event)`: the current power mode.
- `isCoded()`: coding must enable the whole service.

---

## 2. Permanent colour

Three paths. Which one a car uses depends on the model and its coding.

### 2a. Interior ambient strips: `CAmbientLightInteriorColour` (CAN, body module)

`CDevCarInteriorLight::setInteriorLightColor(EMenuInteriorLighting)` → `sendLightInteriorColor()` →
`CPxyCANDevicesAmenity::CAmbientLightInteriorColour::set(...)`. That set message is OpType 0 (Set). Its serialiser
(`0x358800` in libhmil6services) range-checks every field:

| # | Field | Type / allowed range |
|---|---|---|
| 1 | Hue angle | u16, **0–4095** (`0xFFF`, a 12-bit colour wheel) |
| 2 | `EMenuInteriorLighting` (preset) | 0–15 |
| 3–5 | Hue value, layers 1/2/3 (individual groups) | u8 0–255 each |
| 6 | Brightness offset | u8 0–255 |
| 7 | Ambient light mode (`EInterior`) | 0–3 |
| 8 | Dynamic interior lighting (`EInterior`) | 0–3 |
| 9–11 | Reserved | sent as `0xFF` |

- **What stock firmware does:** it copies the last status the body module reported (cached in `CDevCarInteriorLight`
  at `+0x2c`), swaps in the new preset, and sends it back. The hue angle and layer bytes are only echoed.
- **Second version:** `CAmbientLightInteriorColour2` exists alongside it. Dynamic light goes through
  `sendLightInteriorColor2`, and it adds `statusStateDynamicAmbienteInteriorLighting`.
- **User settings message:** `CAmbientLightInteriorUserSetting(2)` carries the rest: Lightsaber brightness and mode,
  ALEV4, panoramic-roof hue (u16), SIA charging touch command, and condition state.
- **Read through CDS:** `libhmiremoting.so` wraps these as `CCdsPropertyAmbientColour` and
  `CCdsPropertyAmbientLightUserSetting`.

**Preset names** (asset folder `Domains/MyVehicle/MyV_Light/ambientlightcolor0bis11`, plus `text.db`):

- **Single colours:** white (`weiss`), orange, bronze, royal blue (`royal_blau`), lilac (`flieder`), mint, green
- **Two-tone:** "White and bronze", "White and orange"
- **Light ensembles:** Classic, Luxury, Modern, Sport, Urban, plus Off. Gated by coding
  `ERWEITERTE_LICHTENSEMBLES`.

The settings screen is `CCarLightInteriorLightActivity` (`selectAmbiColorList`, `selectAmbiOneColorList`).

### 2b. MINI colour switch: `CPxyVehicle::CColorSwitch` / `CColorSwitch2`

`CDevCarLight::setAmbientLightColor(EColorSwitchMenu)` stores the menu value at `+0x104`, then calls
`setColorSwitch()` or `setColorSwitch2()`. Those send `CPxyVehicle::CColorSwitch(2)::set(...)`.

Serialiser for `CColorSwitch2::set` (`0x46babe` in libhmil6services), in argument order:

| # | Arg | Range | Likely meaning |
|---|---|---|---|
| 1 | u16 | 0–65535 | colour value (`statusColoring`) |
| 2 | u8 | 0–15 | possibly saturation or brightness |
| 3 | u8 | 0–255 | brightness / brightness offset |
| 4 | u8 | 0–255 | as above |
| 5 | `ERunningLight` | 0–15 | running (cycling) light mode |
| 6 | `ECSMenu` | 0–15 | **menu selection, the only field the HMI writes** |
| 7 | `EChromaticCircle` | — | colour-wheel selection |
| 8 | `ERunningLightSpeed` | — | cycling speed |
| 9 | `EUIColorScheme` | — | display colour scheme |

The status getters that exist are `Coloring`, `Saturation`, `BrightnessValue`, `BrightnessValueOffset`,
`ChromaticCircle`, `ChromaticCircleWhite`, `CSMenu`, `CSToggle`, `RunningLight`, `RunningLightSpeed` and
`UIColorScheme`. The `ECSMenu` position is confirmed; the meanings of the other fields are inferred from
argument order.

**`ECSMenu` values** (decoded from `CCarInteriorlightRuekoActivity::mapColor` / `mapEnsemble`):

| ECSMenu | Meaning |
|---|---|
| 0 | colour 0 / ensemble 0 |
| 1 | colour 1 |
| 2 | single colour, with a sub-selection: sub 1–4 → colours 2–5, sub 0 → "none" (6) |
| 3–11 | light ensembles 1–9 |
| 12–14 | rejected as invalid |
| 15 | "no selection": `setAmbientLightColor` ignores it |

The MINI `text.db` also has the colour names Sky Blue, Sunrise Yellow, Sunset Orange, Cool Pink, Flashy Green,
Devil Red (and "Heartbeat") near the ambient-light texts (ids 64880–64936). I couldn't tie them to enum values.

### 2c. LED ring permanent mode: `CLEDRing_Settings`

- `CDevCarZIN::setPermanentEnabled(EPermanentGroup, EBackgroundColor)` sends
  `CPxySystemFunctionZIN::CLEDRing_Settings::set(...)`.
- **Fields:** LED-ring switch, animation switch, permanent displays, background colour, permanent switch, and a
  4-bit animation-display bitfield.
- **Permanent groups:** 9 (0–8). The assets in `2D/08_Content_Previews/Ambient_Light_ZIN/zin_perm_anim/` suggest
  gauge-style displays.
- **Background colours:** **6 options (0–5)**. `setPermanentEnabled` maps each through a switch to the bus value.
- **Names unknown:** `CCarDisplaysIkoneRingActivity::getFocusIndex` returns widget IDs (e.g. `0x1ce2`–`0x1ce7` for
  the 6 colours), not text IDs, so I couldn't recover the names.
- **Brightness:** sent separately through `CLEDRing_OffsetBrightnes::set(int8)`.

---

## 3. Can any colour be set (RGB or similar)?

**No RGB field exists anywhere.** The closest are hue/saturation/brightness-style fields:

| Message | Colour fields | Like |
|---|---|---|
| `CAmbientLightInteriorColour` (CAN, body module) | hue angle 0–4095, three per-group hue bytes, brightness offset | hue + brightness, no saturation |
| `CColorSwitch2` (MINI colour switch) | u16 colour value, saturation byte, brightness byte, chromatic circle | close to HSV |
| `CLEDRing_Settings` (LED ring) | background colour 0–5 | presets only |

So in principle you could convert RGB to HSV and send the hue (and, for ColorSwitch2, saturation and brightness).

**Why it's unproven:**

- I checked every caller of the colour send functions:
  - `sendLightInteriorColor`, called by `setInteriorLightColor`, `setInteriorLightBrightness`, `setInteriorLight`
    and `setReducedWhileDriving`
  - `sendLightInteriorColor2`, called by `setInteriorDynamicLight`
  - `setColorSwitch` / `setColorSwitch2`, called by `setAmbientLightColor`, `setAmbientLightBrightnessOffset` and
    `setUIColorScheme`
- All of them copy the last status the module reported and change one field. **None of them writes a hue or
  saturation value it computed itself.**
- So the module turns a preset number into a hue, not the other way round. The hue fields just carry its state back.

**If you send your own hue**, any of these is possible:

- the module uses it, giving a free colour wheel
- the module ignores it and keeps using the preset field
- it only works in a particular mode. "Individual ambient light" is the likely one: there are per-group hue fields
  (`statusHueValueLayer1IndividualGroup` etc.) and a coding flag `INDIVIDUAL_AMBIENTELICHT`, which may need enabling.

Even if hue works, true RGB isn't reachable on the ambient strips. They take hue and brightness but no saturation,
so no pastels or arbitrary whites. White is probably a separate preset.

### How to find out, in order of risk

1. **Read-only:** log the `CAmbientLightInteriorColour` and `CColorSwitch` status messages (or the CDS properties
   `CCdsPropertyAmbientColour` / `CCdsPropertyAmbientLightUserSetting`) while cycling presets in the menu. If the
   hue angle changes with each preset, the module works in hue terms internally, which is a good sign. This also
   shows which path (2a or 2b) the car uses.
2. **One write:** replay the last status with only the hue angle changed and see if the lights follow. This writes
   to the body module, so do it parked, with a known-good preset to restore afterwards.

---

## Coding flags seen (`libhmicoding.so`)

- **Ambient light:** `INDIVIDUAL_AMBIENTELICHT`, `HELLIGKEIT_AMBILIGHT`, `ERWEITERTE_LICHTENSEMBLES`,
  `DEAKTIVIERUNGSMOEGLICHKEIT_AMBILIGHT` (`deaktivierung_bmw` / `deaktivierung_mini`),
  `AMBIENTELICHT_PERMANENTANZEIGE_FES`
- **Lighting features:** `LICHTSCHWERT` (Lightsaber), `WELCOME_LIGHT`
- **Panoramic roof:** `TC_BELEUCHTETES_PANORAMADACH_aktiv_mit_kopplung_an_ambientes_innenlicht` (roof lighting
  linked to the ambient light)
- **Light staging:** `INSZENIERUNG` (`vorstufe`, `vollkonzept_1/2`), `HIGH_END_AUDIO_*_nur_lichtinsz`

## Open questions

- Function IDs for the ZIN and Amenity messages: try `vmostctl list-fblock` or DLT on the car.
- The physical route from vmostd for FBlock `0xD1`.
- Which colour path the car uses (2a or 2b), and whether it accepts arbitrary hue values.
- The names of the 6 LED-ring background colours and the 9 permanent groups.
