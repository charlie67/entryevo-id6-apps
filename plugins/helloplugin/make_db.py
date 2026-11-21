#!/usr/bin/env python3
# Copyright (c) 2026 Charlie Robinson
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Derived from EntryNav2-Android-Auto (Jiraiya43), PolyForm-Noncommercial-1.0.0.
"""Build HelloPlugin's text and image databases.

HelloPlugin_ALL_Texts.zip holds <lang>.txt ("id=text" lines, the format BMW's PluginsCoded apps use) and
HelloPlugin_ALL_Images.zip holds <imageId>.png. The icon and preview images are generated here (no binary
assets in the tree). Both archives are reproducible: same input, same bytes.

Usage: make_db.py <output dir>
"""

import struct
import sys
import zipfile
import zlib
from pathlib import Path

# Text ids must match HelloPlugin.xml. English is the base; a language's own entries override it.
LANGS = {
    "de": "Deutsch",
    "en-UK": "English (UK)",
    "en-US": "English (US)",
    "fr-FR": "Francais",
}
TEXTS = {
    1: "Hello World",
    10: "Change message",
    15: "Demo setting",
    16: "Help",
    20: "A hello-world iDrive plugin skeleton.",
    21: "Entry row -> this menu -> a live label.",
    22: "The label text is set with updateModel.",
    23: "MENU: iDrive  -  BACK: back",
}
LANG_TEXTS = {  # ASCII only
    "fr-FR": {
        10: "Changer le message",
        15: "Reglage de demonstration",
        16: "Aide",
        20: "Un squelette de plugin iDrive hello-world.",
        21: "Ligne d'entree -> ce menu -> un libelle.",
        22: "Le texte est defini avec updateModel.",
        23: "MENU : iDrive  -  BACK : retour",
    },
    "de": {
        10: "Nachricht wechseln",
        15: "Demo-Einstellung",
        16: "Hilfe",
        20: "Ein Hello-World iDrive-Plugin-Geruest.",
        21: "Eintrag -> dieses Menue -> ein Label.",
        22: "Der Text wird mit updateModel gesetzt.",
        23: "MENU: iDrive  -  BACK: zurueck",
    },
}
FIXED_DATE = (2026, 11, 20, 0, 0, 0)  # the same date in every archive: reproducible files


def add(archive, name, data):
    """Store one member, compressed, with the fixed date."""
    info = zipfile.ZipInfo(name, FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def png(width, height, rgba_rows):
    """Encode an RGBA PNG from a list of `height` rows, each `width` (r,g,b,a) tuples, with no image library."""

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    for row in rgba_rows:
        raw.append(0)  # filter type 0
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))
    return (
        bytes([0x89])
        + b"PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def panel_png(width, height, fill, border, border_px=2):
    """A solid `fill` rectangle with a `border`-coloured frame -- a plain, recognisable placeholder."""
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            edge = x < border_px or y < border_px or x >= width - border_px or y >= height - border_px
            row.append(border if edge else fill)
        rows.append(row)
    return png(width, height, rows)


def write_texts(path):
    with zipfile.ZipFile(path, "w") as archive:
        for lang, langname in LANGS.items():
            texts = dict(TEXTS)
            texts.update(LANG_TEXTS.get(lang, {}))
            body = f"100000={langname}\n" + "".join(f"{key}={value}\n" for key, value in sorted(texts.items()))
            if not body.isascii():
                raise SystemExit(f"FAIL: {lang} texts must stay ASCII")
            add(archive, lang + ".txt", body.encode("utf-8"))


def write_images(path):
    with zipfile.ZipFile(path, "w") as archive:
        # Entry-row icon and the side preview, generated as plain BMW-blue panels.
        add(archive, "56001.png", panel_png(63, 54, (0, 90, 160, 255), (255, 255, 255, 255)))
        add(archive, "56002.png", panel_png(549, 484, (20, 30, 45, 255), (0, 120, 200, 255), border_px=6))


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: make_db.py <output dir>")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    write_texts(out / "HelloPlugin_ALL_Texts.zip")
    write_images(out / "HelloPlugin_ALL_Images.zip")
    print("wrote HelloPlugin_ALL_Texts.zip, HelloPlugin_ALL_Images.zip in", out)


if __name__ == "__main__":
    main()
