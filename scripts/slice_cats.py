"""Crop the kawaii sticker sheet into transparent pose PNGs.

Pixels are only cropped and the baked checkerboard is cleared to alpha.
No new artwork is drawn.
"""
from __future__ import annotations

from pathlib import Path
import shutil

from PIL import Image

SHEET = Path(
    r"C:\Users\sindh\.cursor\projects\c-Users-sindh-Desktop-reborn\assets"
    r"\c__Users_sindh_AppData_Roaming_Cursor_User_workspaceStorage_dd6cd7dc65ada9289b46b522152a76c2_images_Kawaii_Pixel_Cat_Sticker_Sheet-09f2ac07-5e98-4aa8-9850-41c1ba35a605.jpg"
)
OUT = Path(r"C:\Users\sindh\Desktop\reborn\widget\src\assets\character")
CANVAS = (240, 248)
BOTTOM_PAD = 8

# Body index -> pose. celebrate is a copy of cheer (same sticker).
POSES = {
    0: "idle_sit",
    1: "wave",
    2: "cheer",
    3: "playful",
    4: "jump_happy",
    5: "stretch",
    6: "perk_up",
    7: "box",
    8: "sleep",
    9: "roll",
    10: "confused",
    11: "heart",
    12: "cheeks",
    13: "idle_blink",
    14: "dig2",
    15: "walk",
    16: "lightbulb",
    17: "point",
    18: "walk_to_edge",
    19: "dig",
    20: "loaf",
    21: "scarf",
    22: "hood",
    23: "think",
    24: "smile",
    25: "eat",
    26: "peek",
}


def is_clear(r: int, g: int, b: int) -> bool:
    return abs(r - g) < 22 and abs(g - b) < 22 and r > 165


def components(im: Image.Image) -> list[tuple[int, int, int, int, int]]:
    w, h = im.size
    px = im.load()
    assert px is not None
    seen = bytearray(w * h)
    found: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or is_clear(*px[x, y]):
                continue
            stack = [(x, y)]
            seen[i] = 1
            minx = maxx = x
            miny = maxy = y
            n = 0
            while stack:
                cx, cy = stack.pop()
                n += 1
                minx = min(minx, cx)
                maxx = max(maxx, cx)
                miny = min(miny, cy)
                maxy = max(maxy, cy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    j = ny * w + nx
                    if seen[j] or is_clear(*px[nx, ny]):
                        continue
                    seen[j] = 1
                    stack.append((nx, ny))
            if n > 4000:
                found.append((n, minx, miny, maxx, maxy))
    found.sort(key=lambda item: (item[2], item[1]))
    return found


def knock_out(crop: Image.Image) -> Image.Image:
    rgba = crop.convert("RGBA")
    w, h = rgba.size
    pix = rgba.load()
    assert pix is not None
    bg = bytearray(w * h)
    stack: list[tuple[int, int]] = []
    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        i = y * w + x
        if bg[i]:
            continue
        r, g, b, _a = pix[x, y]
        if not is_clear(r, g, b):
            continue
        bg[i] = 1
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for y in range(h):
        for x in range(w):
            if bg[y * w + x]:
                r, g, b, _a = pix[x, y]
                pix[x, y] = (r, g, b, 0)
    return rgba


def trim(im: Image.Image) -> Image.Image:
    alpha = im.getchannel("A")
    box = alpha.getbbox()
    if box is None:
        return im
    return im.crop(box)


def place(sprite: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    sw, sh = sprite.size
    x = (CANVAS[0] - sw) // 2
    y = CANVAS[1] - sh - BOTTOM_PAD
    if y < 0:
        y = 0
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def main() -> None:
    sheet = Image.open(SHEET).convert("RGB")
    bodies = components(sheet)
    if len(bodies) != len(POSES):
        raise SystemExit(f"expected {len(POSES)} cats, found {len(bodies)}")
    preview = OUT / "_preview"
    if preview.exists():
        shutil.rmtree(preview)
    OUT.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Image.Image] = {}
    for index, (_n, x0, y0, x1, y1) in enumerate(bodies):
        crop = sheet.crop((max(0, x0 - 4), max(0, y0 - 4), min(sheet.width, x1 + 5), min(sheet.height, y1 + 5)))
        sprite = place(trim(knock_out(crop)))
        name = POSES[index]
        sprite.save(OUT / f"{name}.png")
        saved[name] = sprite
        print(name, sprite.getchannel("A").getbbox())
    saved["cheer"].save(OUT / "celebrate.png")
    print("celebrate copied from cheer")


if __name__ == "__main__":
    main()
