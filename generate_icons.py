"""Generate PNG icons for the Chrome extension from scratch (no external deps)."""
import struct
import zlib
import os

def create_png(width, height, rgba_data):
    """Create a minimal PNG file from RGBA pixel data."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = b""
    for y in range(height):
        raw += b"\x00"  # filter byte
        for x in range(width):
            idx = (y * width + x) * 4
            raw += bytes(rgba_data[idx:idx+4])

    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def draw_icon(size):
    """Draw a purple rounded-rect icon with a magnifying glass + checkmark."""
    pixels = [0] * (size * size * 4)

    def set_pixel(x, y, r, g, b, a=255):
        if 0 <= x < size and 0 <= y < size:
            idx = (y * size + x) * 4
            # Alpha blend
            old_a = pixels[idx+3]
            if old_a == 0:
                pixels[idx] = r; pixels[idx+1] = g; pixels[idx+2] = b; pixels[idx+3] = a
            else:
                fa = a / 255.0
                pixels[idx] = int(r * fa + pixels[idx] * (1-fa))
                pixels[idx+1] = int(g * fa + pixels[idx+1] * (1-fa))
                pixels[idx+2] = int(b * fa + pixels[idx+2] * (1-fa))
                pixels[idx+3] = min(255, old_a + a)

    def fill_circle(cx, cy, radius, r, g, b, a=255):
        for y in range(max(0, int(cy-radius-1)), min(size, int(cy+radius+2))):
            for x in range(max(0, int(cx-radius-1)), min(size, int(cx+radius+2))):
                dist = ((x - cx)**2 + (y - cy)**2)**0.5
                if dist <= radius:
                    set_pixel(x, y, r, g, b, a)

    def draw_circle_ring(cx, cy, radius, thickness, r, g, b):
        for y in range(size):
            for x in range(size):
                dist = ((x - cx)**2 + (y - cy)**2)**0.5
                if abs(dist - radius) <= thickness / 2:
                    set_pixel(x, y, r, g, b)

    def draw_line(x0, y0, x1, y1, thickness, r, g, b):
        steps = max(abs(x1-x0), abs(y1-y0), 1) * 3
        for i in range(int(steps)+1):
            t = i / steps
            px = x0 + (x1-x0) * t
            py = y0 + (y1-y0) * t
            for dy in range(-int(thickness), int(thickness)+1):
                for dx in range(-int(thickness), int(thickness)+1):
                    if dx*dx + dy*dy <= thickness*thickness:
                        set_pixel(int(px+dx), int(py+dy), r, g, b)

    # Background: purple gradient rounded rect
    corner_r = size * 0.15
    for y in range(size):
        for x in range(size):
            # Check if inside rounded rect
            inside = True
            if x < corner_r and y < corner_r:
                inside = (x-corner_r)**2 + (y-corner_r)**2 <= corner_r**2
            elif x >= size-corner_r and y < corner_r:
                inside = (x-(size-corner_r))**2 + (y-corner_r)**2 <= corner_r**2
            elif x < corner_r and y >= size-corner_r:
                inside = (x-corner_r)**2 + (y-(size-corner_r))**2 <= corner_r**2
            elif x >= size-corner_r and y >= size-corner_r:
                inside = (x-(size-corner_r))**2 + (y-(size-corner_r))**2 <= corner_r**2
            if inside:
                # Gradient from #6366f1 to #8b5cf6 (top-left to bottom-right)
                t = (x + y) / (2 * size)
                r = int(99 + (139 - 99) * t)   # 99 -> 139
                g = int(102 + (92 - 102) * t)   # 102 -> 92
                b = int(241 + (246 - 241) * t)  # 241 -> 246
                set_pixel(x, y, r, g, b)

    s = size / 128.0  # scale factor

    # Magnifying glass circle
    cx, cy, cr = 52*s, 52*s, 26*s
    draw_circle_ring(cx, cy, cr, max(2, 5*s), 255, 255, 255)

    # Magnifying glass handle
    draw_line(72*s, 72*s, 100*s, 100*s, max(1.5, 3.5*s), 255, 255, 255)

    # Checkmark inside
    if size >= 32:
        draw_line(40*s, 54*s, 50*s, 64*s, max(1, 2.5*s), 255, 255, 255)
        draw_line(50*s, 64*s, 66*s, 42*s, max(1, 2.5*s), 255, 255, 255)

    return pixels


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "chrome_extension", "icons")
    os.makedirs(out_dir, exist_ok=True)

    for sz in [16, 48, 128]:
        pixels = draw_icon(sz)
        png_data = create_png(sz, sz, pixels)
        path = os.path.join(out_dir, f"icon{sz}.png")
        with open(path, "wb") as f:
            f.write(png_data)
        print(f"Generated {path} ({len(png_data)} bytes)")
