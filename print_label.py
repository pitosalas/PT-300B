#!/usr/bin/env python3
"""Print text labels on a Brother PT-P300BT over its Bluetooth serial port.

Each positional argument is one line of text.

Examples:
  print_label.py "Hello"
  print_label.py "you@example.com" "555-123-4567" --length-in 1.5 --copies 3
  print_label.py "Spices" --font "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
  print_label.py "Test" --preview          # writes preview.png, does not touch the printer
"""
import argparse
import os
import struct
import sys
import time

from PIL import Image, ImageDraw, ImageFont

from status import PORT, open_port, read_exact, decode

DPI = 180
HEAD_PINS = 128                      # print head width in dots
LINE_BYTES = HEAD_PINS // 8
# tape width (mm) -> (printable pins, margin pins on each side)
TAPE_PINS = {3: (24, 52), 6: (32, 48), 9: (50, 39), 12: (70, 29)}
DEFAULT_FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
FEED_DOTS = 14                       # printer's leading/trailing margin, ~2 mm
PAD = 8                              # blank dots between text and label edge
LINE_SPACING = 1.08


def dots(mm):
    return round(mm / 25.4 * DPI)


def layout(lines, font_path, size):
    """Return (font, line boxes, block width, block height) for a font size."""
    font = ImageFont.truetype(font_path, size=size)
    boxes = [font.getbbox(line) for line in lines]
    line_h = round(size * LINE_SPACING)
    width = max(b[2] - b[0] for b in boxes)
    height = line_h * (len(lines) - 1) + max(b[3] for b in boxes) - min(b[1] for b in boxes)
    return font, boxes, width, height, line_h


def fit_font(lines, font_path, height, max_width):
    """Largest font size whose text block fits within height x max_width."""
    best = None
    for size in range(4, 200):
        font, boxes, w, h, lh = layout(lines, font_path, size)
        if h > height or (max_width is not None and w > max_width):
            break
        best = (size, font, boxes, w, h, lh)
    if best is None:
        sys.exit("Text cannot fit on this label even at the smallest font size.")
    return best


def render_label(lines, height, font_path, length=None):
    """Render one label. length (dots) fixes the label length; text shrinks to fit."""
    max_w = None if length is None else length - 2 * PAD
    size, font, boxes, w, h, lh = fit_font(lines, font_path, height, max_w)
    width = length if length is not None else w + 2 * PAD
    img = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(img)
    top = (height - h) // 2
    for i, (line, box) in enumerate(zip(lines, boxes)):
        x = (width - (box[2] - box[0])) // 2 - box[0]
        y = top + i * lh - min(b[1] for b in boxes)
        draw.text((x, y), line, font=font, fill=0)
    return img, size


def strip_with_cut_marks(label, copies):
    """Join copies into one strip with dotted cut lines at every label boundary."""
    width = label.width * copies + copies + 1
    strip = Image.new("1", (width, label.height), 1)
    x = 0
    for _ in range(copies):
        draw_cut_mark(strip, x)
        strip.paste(label, (x + 1, 0))
        x += label.width + 1
    draw_cut_mark(strip, x)
    return strip


def draw_cut_mark(img, x):
    for y in range(0, img.height, 4):
        for dy in range(2):
            if y + dy < img.height:
                img.putpixel((x, y + dy), 0)


def raster_lines(img, margin):
    """One raster line per image column; black pixel -> bit set."""
    px = img.load()
    for x in range(img.width):
        bits = 0
        for y in range(img.height):
            if px[x, y] == 0:
                bits |= 1 << (HEAD_PINS - 1 - (margin + y))
        yield bits.to_bytes(LINE_BYTES, "big")


def encode_line(line):
    if not any(line):
        return b"\x5a"                                   # blank raster line
    packed = bytes([LINE_BYTES - 1]) + line              # PackBits literal run
    return b"\x47" + struct.pack("<H", len(packed)) + packed


def build_job(img, tape_mm, margin):
    lines = list(raster_lines(img, margin))
    job = bytearray()
    job += b"\x00" * 100                                 # invalidate
    job += b"\x1b\x40"                                   # initialize
    job += b"\x1b\x69\x61\x01"                           # raster mode
    job += (b"\x1b\x69\x7a" + bytes([0x84, 0x00, tape_mm, 0x00])
            + struct.pack("<I", len(lines)) + b"\x00\x00")  # print information
    job += b"\x1b\x69\x4d\x00"                           # various mode: no auto-cut
    job += b"\x1b\x69\x4b\x00"                           # advanced mode
    job += b"\x1b\x69\x64" + struct.pack("<H", FEED_DOTS)  # margin
    job += b"\x4d\x02"                                   # TIFF compression
    for line in lines:
        job += encode_line(line)
    job += b"\x1a"                                       # print with feed
    return bytes(job)


def query_status(fd):
    os.write(fd, b"\x00" * 100 + b"\x1b\x40\x1b\x69\x53")
    reply = read_exact(fd, 32, timeout=10)
    if len(reply) != 32:
        sys.exit(f"No status reply (got {len(reply)} bytes)")
    return decode(reply)


def build_image(args, tape_mm):
    pins, _ = TAPE_PINS[tape_mm]
    length = None
    if args.length_in:
        length = dots(args.length_in * 25.4)
    elif args.length_mm:
        length = dots(args.length_mm)
    label, size = render_label(args.lines, pins, args.font, length)
    img = strip_with_cut_marks(label, args.copies) if args.copies > 1 else label
    img.save(args.preview_path)
    mm = label.width / DPI * 25.4
    print(f"Tape {tape_mm} mm | {len(args.lines)} line(s) | font size {size}px | "
          f"label {mm:.0f} mm ({mm / 25.4:.2f} in) x {args.copies} | preview: {args.preview_path}")
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines", nargs="+", help="one argument per line of text")
    ap.add_argument("--length-in", type=float, help="fixed label length in inches")
    ap.add_argument("--length-mm", type=float, help="fixed label length in mm")
    ap.add_argument("--copies", type=int, default=1, help="print N labels on one strip with cut marks")
    ap.add_argument("--font", default=DEFAULT_FONT, help="path to a .ttf/.ttc/.otf font")
    ap.add_argument("--preview", action="store_true", help="only write the preview image; don't print")
    ap.add_argument("--tape-mm", type=int, default=9, help="tape width for --preview (default 9)")
    ap.add_argument("--preview-path", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview.png"))
    args = ap.parse_args()

    if args.preview:
        build_image(args, args.tape_mm)
        return

    fd = open_port(PORT)
    try:
        status = query_status(fd)
        tape_mm = status["tape width (mm)"]
        if status["errors"] != ["none"] or tape_mm not in TAPE_PINS:
            sys.exit(f"Printer not ready: {status}")
        img = build_image(args, tape_mm)
        os.write(fd, build_job(img, tape_mm, TAPE_PINS[tape_mm][1]))
        deadline = time.time() + 60
        while time.time() < deadline:
            msg = read_exact(fd, 32, timeout=deadline - time.time())
            if len(msg) < 32:
                print("  no further reply from printer")
                break
            info = decode(msg)
            print("  printer:", info["status type"], "| errors:", info["errors"])
            if info["status type"] in ("printing completed", "error"):
                break
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
