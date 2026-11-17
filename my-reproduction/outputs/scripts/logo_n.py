"""Build the N logo from library parts -- no voxelising this time.

The logo's N is wide and flat (about 1.26:1), so the model is 14 studs wide
and nine layers tall. The diagonal steps one stud sideways per layer, which a
45-degree slope brick (3039 or its mirror 3040) covers smoothly; a plain 1x2
behind each slope gives the stroke its body.
"""
from pathlib import Path

STUD = 20.0
BRICK = 24.0

CYAN, AQUA, BLUE = "322", "118", "1"
ROT_CW = "0 0 1 0 1 0 -1 0 0"     # part's long edge (Z) turned onto X
ROT_CCW = "0 0 -1 0 1 0 1 0 0"    # the same, flipped end for end


def build(out, width=14, height=9, depth=2, slope="3039", flip=False):
    x0 = width / 2.0
    z0 = depth / 2.0
    lines = ["0 FILE n-logo.ldr", "0 Name: n-logo.ldr",
             "0 Author: ldraw-nova logo builder (library parts)"]

    def add(part, colour, x, y, z, rot="1 0 0 0 1 0 0 0 1"):
        lines.append(f"1 {colour} {x:.1f} {y:.1f} {z:.1f} {rot} {part}.dat")

    def colour(k):
        return CYAN if k >= 6 else AQUA if k >= 3 else BLUE

    rot = ROT_CCW if flip else ROT_CW
    diag_layers = height - 2          # diagonal spans all but the top row
    for k in range(height):
        c = colour(k)
        y = -(k * BRICK + BRICK / 2)
        add("3003", c, (1 - x0) * STUD, y, 0.0)
        add("3003", c, (width - 2 - x0) * STUD, y, 0.0)
        if k < diag_layers:
            # Slope faces down-right along the stroke; the 1x2 behind it is
            # the stroke's body, so the diagonal is three studs thick.
            x_slope = (9 - k + 1 - x0) * STUD     # spans cols 9-k .. 10-k
            for j in range(depth):
                z = (j + 0.5 - z0) * STUD
                add(slope, c, x_slope, y, z, rot)
            add("3004", c, (11 - k + 0.5 - x0) * STUD, y, 0.0)
        # The stroke's top end meets the left column; without this stud a
        # one-stud gap opens between them on the top two diagonal rows.
        if diag_layers - 2 <= k < diag_layers:
            add("3004", c, (2.5 - x0) * STUD, y, 0.0)
    lines.append("0 NOFILE")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sum(1 for l in lines if l.startswith("1 "))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output/logo-n/n-logo.ldr")
    ap.add_argument("--slope", default="3039", choices=("3039", "3040"))
    ap.add_argument("--flip", action="store_true",
                    help="mirror the slope; the N wants the default")
    args = ap.parse_args()
    n = build(args.out, slope=args.slope, flip=args.flip)
    print(f"wrote {args.out}: {n} parts")
