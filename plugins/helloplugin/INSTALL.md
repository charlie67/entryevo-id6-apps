# Installing HelloPlugin

The root filesystem `/` is mounted read-only and the plugin **must** live on it (`/var/local` is `noexec`, so
`dlopen` fails there). The procedure remounts `/` read-write only for the copy, then back to read-only.

Access the unit with an ENET cable (OBD→Ethernet), then `ssh root@169.254.1.0`.

## 1. Build the archive (on the Mac)

```sh
../../hmitest/build-plugin.sh . make        # libHelloPlugin.so (ARM)
../../hmitest/test-plugin.sh ./libHelloPlugin.so   # must print RESULT: PASS
python3 -I package.py                    # artifacts/helloplugin-armhf.tar
```

## 2. Copy and verify (on the Mac)

```sh
scp artifacts/helloplugin-armhf.tar root@169.254.1.0:/tmp/
```

## 3. Install (on the unit, over SSH)

```sh
cd /tmp
mkdir -p hp && tar -xf helloplugin-armhf.tar -C hp && cd hp
md5sum -c MD5SUMS                                   # must say: OK for every file

mount -o remount,rw /
mkdir -p /opt/hmi/data/ro/Plugins/HelloPlugin
cp opt/hmi/data/ro/Plugins/HelloPlugin/* /opt/hmi/data/ro/Plugins/HelloPlugin/
chmod 755 /opt/hmi/data/ro/Plugins/HelloPlugin/libHelloPlugin.so
sync
mount -o remount,ro /

# Pre-flight: confirm every symbol resolves against the car's own libraries WITHOUT running the plugin.
# This must print nothing; anything here means do NOT reboot (remove the folder first, see Uninstall).
L=/usr/local/lib:/opt/hmi/lib:/usr/lib:/lib
LD_TRACE_LOADED_OBJECTS=1 LD_WARN=yes LD_BIND_NOW=yes LD_LIBRARY_PATH=$L \
    /lib/ld-linux-armhf.so.3 /opt/hmi/data/ro/Plugins/HelloPlugin/libHelloPlugin.so \
    2>&1 | grep -E 'not found|undefined symbol|not defined in file'

# Optional: turn on logging (app.log and cds.log under the data dir).
mkdir -p /var/local/data/HelloPlugin
touch /var/local/data/HelloPlugin/maintenance

reboot
```

After the reboot, open **My Vehicle** — a **"Hello World"** row should appear. Select it for the demo menu.

## 4. Check the logs (only if `maintenance` is present)

```sh
cat /var/local/data/HelloPlugin/app.log      # create/onInit/handler activity
cat /var/local/data/HelloPlugin/cds.log      # which CDS properties this car fills, and their JSON
```

If the row does not appear, the HMI loader logs its reason over DLT (see `../../NOTES.md` §2, §5). The row is
added anchorless, so it sits at/near the bottom of the My Vehicle list.

## Uninstall

```sh
mount -o remount,rw /
rm -rf /opt/hmi/data/ro/Plugins/HelloPlugin
mount -o remount,ro /
rm -rf /var/local/data/HelloPlugin          # settings and logs (optional)
reboot
```

The plugin is entirely contained in those two folders — removing them restores the unit to stock. A firmware
update also wipes `/opt/hmi/...`, so it would remove the plugin on its own.

**Disable without uninstalling** (keeps the files, just stops it loading): `touch
/var/local/data/HelloPlugin/app.disable` and reboot; delete that file and reboot to re-enable.

## Recovery (if the UI misbehaves)

```sh
ssh root@169.254.1.0
touch /var/local/data/HelloPlugin/app.disable   # keeps the plugin off; the HMI starts without it
reboot
```

The crash guard also turns the plugin off by itself after 3 short HMI runs; remove
`/var/local/data/HelloPlugin/app-guard` once the logs are checked. As a last resort, hold the iDrive power knob
for ~30 s.
