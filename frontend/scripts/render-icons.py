"""Draw the Ghostline home-screen icons. No font or image library required."""

import pathlib
import struct
import zlib

# A 16x12 wordmark. The mark stays inside the center so a maskable crop still shows it.
MARK = (
    "                ",
    "                ",
    "   #####  #     ",
    "  #     # #     ",
    "  #     # #     ",
    "  # ####  #     ",
    "  #  #    #     ",
    "   ##     ###   ",
    "                ",
    "                ",
    "                ",
    "                ",
)
BG = (0x1B, 0x1F, 0x23, 255)
INK = (0x8F, 0xB9, 0xA8, 255)


def write_png(path, size):
    rows = len(MARK)
    cols = len(MARK[0])
    cell = max(1, size // 24)
    mark_w = cols * cell
    mark_h = rows * cell
    origin_x = (size - mark_w) // 2
    origin_y = (size - mark_h) // 2
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        gy = y - origin_y
        for x in range(size):
            gx = x - origin_x
            on = (
                0 <= gx < mark_w
                and 0 <= gy < mark_h
                and MARK[gy // cell][gx // cell] == "#"
            )
            raw.extend(INK if on else BG)
    png = bytearray(b"\x89PNG\r\n\x1a\n")

    def chunk(tag, data):
        png.extend(struct.pack(">I", len(data)))
        png.extend(tag)
        png.extend(data)
        png.extend(struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    chunk(b"IEND", b"")
    path.write_bytes(png)


def main():
    out = pathlib.Path(__file__).resolve().parents[1] / "public" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    write_png(out / "icon-192.png", 192)
    write_png(out / "icon-512.png", 512)
    write_png(out / "apple-touch-icon.png", 180)


if __name__ == "__main__":
    main()
