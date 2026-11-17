"""Build the Huawei logo wall as a brick mosaic -- vector, not voxelised.

Eight petals are rasterised straight from polar geometry (a fan of sectors
around a point below the logo), the HUAWEI letters come from a 5x7 dot font,
and every pixel is a 1x1 plate on a blue 32x32 base. Petals get a second
layer of 1x1 bricks so they stand proud of the letters, like the real wall.

The file is grouped with STEP markers (base / petal / letter) so the assembly
video installs the logo petal by petal.
"""
import math
from pathlib import Path

STUD = 20.0
W = H = 32
BLUE, GRAY, WHITE = "1", "71", "15"

FONT = {
    'H': ["X...X", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    'U': ["X...X", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    'A': [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    'W': ["X...X", "X...X", "X.X.X", "X.X.X", "X.X.X", "XX.XX", "X...X"],
    'E': ["XXXX.", "X....", "X....", "XXX..", "X....", "X....", "XXXX."],
    'I': ["XXX", ".X.", ".X.", ".X.", ".X.", ".X.", "XXX"],
}


def petal_pixels():
    """Petal k of eight, rasterised from polar coordinates.

    The fan centre sits low in the grid so the blooms open away from the
    letters, which occupy the bottom rows.
    """
    cx, cy = 15.5, 12.5
    out = {}
    for i in range(W):
        for j in range(H):
            dx, dy = i - cx, j - cy
            r = math.hypot(dx, dy)
            if not 2.5 <= r <= 17.0:
                continue
            phi = math.degrees(math.atan2(dy, dx))
            k = round((phi - 11.25) / 22.5)
            if 0 <= k <= 7 and abs(phi - (11.25 + 22.5 * k)) <= 7.0:
                out[(i, j)] = k
    return out


def letter_pixels():
    out = {}
    x = 0
    for ch in "HUAWEI":
        glyph = FONT[ch]
        for row, cells in enumerate(glyph):          # row 0 is the top
            for col, cell in enumerate(cells):
                if cell == 'X':
                    out[(x + col, 7 - row)] = ch
        x += len(glyph[0]) + 1                       # glyph width, not rows
    return out


def build(out_path):
    petals = petal_pixels()
    letters = letter_pixels()

    lines = ["0 FILE huawei-logo.ldr", "0 Name: huawei-logo.ldr",
             "0 Author: ldraw-nova mosaic builder"]

    def add(part, colour, i, j, y):
        x = (i + 0.5 - W / 2) * STUD
        z = (j + 0.5 - H / 2) * STUD
        lines.append(f"1 {colour} {x:.1f} {y:.1f} {z:.1f} "
                     f"1 0 0 0 1 0 0 0 1 {part}.dat")

    # Base: four 16x16 plates in brand blue.
    for qi in (0, 16):
        for qj in (0, 16):
            lines.append(f"1 {BLUE} {(qi + 8 - W / 2) * STUD:.1f} 4.0 "
                         f"{(qj + 8 - H / 2) * STUD:.1f} "
                         f"1 0 0 0 1 0 0 0 1 91405.dat")
    lines.append("0 STEP")
    # Petals, one STEP per petal: plate layer then the raised brick layer.
    # LDraw Y grows downward, so layers above the base get negative Y.
    for k in range(8):
        for (i, j), pk in petals.items():
            if pk != k:
                continue
            add("3024", GRAY, i, j, -4.0)
        for (i, j), pk in petals.items():
            if pk != k:
                continue
            add("3005", GRAY, i, j, -12.0)
        lines.append("0 STEP")
    # Letters, one STEP per glyph.
    for ch in "HUAWEI":
        for (i, j), lc in letters.items():
            if lc == ch:
                add("3024", WHITE, i, j, -4.0)
        lines.append("0 STEP")
    lines.append("0 NOFILE")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(1 for l in lines if l.startswith("1 "))
    print(f"wrote {out}: {n} parts "
          f"({len(petals)} petal px, {len(letters)} letter px)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/huawei-logo/huawei-logo.ldr")
    args = ap.parse_args()
    build(args.out)
