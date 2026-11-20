# entryevo-id6-apps

Tooling and research for writing **custom iDrive plugins** on a rooted BMW **EntryEVO (ID5/ID6)** head unit.

The unit loads native-style "RHMI" plugins (a `.so` + manifest/XML dropped into
`/opt/hmi/data/ro/Plugins/`) directly into the `HmiMain3D` UI process. The goal here is a working
hello-world plugin, then reading car data (CDS) and talking to other vehicle modules.

Inspired by:
- [inotbarnacle/ID6_apps_prerelease](https://github.com/inotbarnacle/ID6_apps_prerelease)
- [Jiraiya43/EntryNav2-Android-Auto](https://github.com/Jiraiya43/EntryNav2-Android-Auto) — the reference RHMI plugin (PolyForm Noncommercial 1.0.0)

## Target

- **Unit:** BMW EntryEVO head unit (TI Jacinto 6 SoC), ARMv7 hard-float, Linux 3.12.25, glibc 2.15,
  BusyBox + systemd.
- **Firmware surveyed:** `202402191339` (`EntryEvo_ID5_2403_Release`).
- **Access:** ENET cable (OBD→Ethernet), then `ssh root@169.254.1.0`. Root `/` is read-only
  (remount rw only to install); code must live on `/`.

## Status

- ✅ Surveyed and dumped the unit; plugin framework ABI (vtable slots 21/22/23, constructor)
  verified against this firmware.
- ✅ Mapped CDS properties and SOME/IP / vMOST links to other modules (from the dump only).
- ✅ Emulated load/ABI test harness working (`hmitest/`); reference plugin passes.

See [`NOTES.md`](./NOTES.md) for the detailed breakdown.
