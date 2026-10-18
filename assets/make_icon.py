"""Generate the concentric-rings .ico (matches the tray icon) with stdlib only."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tray  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def dib_entry(size: int, pixels: bytes) -> bytes:
    xor = bytearray()
    for y in range(size - 1, -1, -1):
        xor += pixels[y * size * 4:(y + 1) * size * 4]

    mask_stride = ((size + 31) // 32) * 4
    mask = bytearray(mask_stride * size)
    for y in range(size):
        for x in range(size):
            if pixels[(y * size + x) * 4 + 3] < 128:
                mask[(size - 1 - y) * mask_stride + (x // 8)] |= 0x80 >> (x % 8)

    hdr = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    return hdr + bytes(xor) + bytes(mask)


def build_ico(mouse: int, keyboard: int) -> bytes:
    images = []
    for size in SIZES:
        images.append((size, dib_entry(size, tray.render_pixels(mouse, keyboard, size))))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    directory = bytearray()
    blobs = bytearray()
    for size, image in images:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(image), offset)
        offset += len(image)
        blobs += image
    return header + bytes(directory) + bytes(blobs)


def main():
    out = Path(__file__).with_name("battery.ico")
    out.write_bytes(build_ico(86, 72))
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
