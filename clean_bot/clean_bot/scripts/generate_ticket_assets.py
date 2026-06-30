"""Generate ticket banner PNGs (run once). Place your logo at assets/tickets/logo.png."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "tickets"

WIDTH = 1400
HEIGHT = 48

BANNERS: dict[str, tuple[int, int, int]] = {
    "banner_red.png": (227, 6, 19),
    "banner_orange.png": (255, 140, 0),
    "banner_yellow.png": (255, 220, 0),
    "banner_green.png": (57, 255, 20),
    "banner_blue.png": (30, 144, 255),
    "banner_purple.png": (138, 122, 224),
    "banner_brown.png": (139, 90, 43),
    "banner_white.png": (238, 238, 238),
    "banner_black.png": (0, 0, 0),
}


def _png_rgb(path: Path, rgb: tuple[int, int, int]) -> None:
    r, g, b = rgb
    row = b"\x00" + bytes([r, g, b]) * WIDTH
    raw = row * HEIGHT
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rgb in BANNERS.items():
        _png_rgb(OUT / name, rgb)
        print(f"Wrote {OUT / name}")
    logo = OUT / "logo.png"
    if logo.is_file():
        print(f"Logo already present at {logo}")
    else:
        print(f"Add your SQR logo at {logo}")


if __name__ == "__main__":
    main()
