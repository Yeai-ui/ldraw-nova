"""Original model v2: a corner coffee kiosk.

Everything here is COMPUTED, not hand-typed. Three conventions are encoded
once and reused everywhere:

  1. LDraw placement semantics -- `at:[x,Y,z]` puts the part's TOP FACE at Y;
     the body occupies [Y, Y+height]. So stacking UP means subtracting.
     Example: the first brick course sits on the base plate and goes at
     Y = -BRICK (-24), not -PLATE.
  2. Part footprints -- read from ldraw_tools/data/rectangular-parts.json,
     e.g. 3009 "Brick 1 x 6" is x_studs=6, z_studs=1 -> one might reasonably
     assume the reverse from the name alone.
  3. Ring tiling -- walls are 1 stud thick and must tile the perimeter with
     EXACTLY abutting envelopes (no overlap), because the body-overlap check
     has no tolerance for interlocking brick bonds.

Run:  python output/generate_kiosk_v2.py --output output/kiosk_v2.plan.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AUTHOR = "Ye Shuai - LDraw Nova route B self-test"

# --- LDraw geometry constants (LDU) -----------------------------------------
STUD = 20           # stud pitch
PLATE = 8           # plate body height
BRICK = 24          # brick body height

# --- palette ----------------------------------------------------------------
C_BASE = 71         # Light Bluish Gray
C_WALL = 5          # Brick Red
C_TRIM = 19         # Tan
C_ROOF = 2          # Green
C_GLASS = 47        # Trans Clear
C_DOOR = 6          # Green
C_FRAME = 19        # Tan - must be set on module REFERENCES (see note below)
C_CHIMNEY = 0       # Black

# --- envelope ---------------------------------------------------------------
# Footprint is a true 12 x 12 stud square. NOTE: 3028 is "Plate 6 x 12", i.e.
# 6 studs along Z and 12 along X, so the square needs the two plates stacked
# along Z (z = -60 / +60), NOT side by side along X (that yields 24 x 6 --
# the bug that sank v1).
HALF = 120                     # half of 12 studs
WALL_OFF = HALF - 10           # 110: centreline of a 1-stud-thick wall
X_LEFT, X_RIGHT = -WALL_OFF, WALL_OFF
Z_BACK, Z_FRONT = -WALL_OFF, WALL_OFF
INNER = HALF - STUD            # 100: where the side runs stop (corners belong
                               #      to the front/back runs)

LAYERS = 6                     # six brick courses = 144 LDU, same as a door
WINDOW_COURSES = (2, 3)        # 0-indexed courses occupied by the glazing


def course_top(i: int) -> float:
    """Top face of brick course `i` (0 = bottom)."""
    return -float(BRICK * (i + 1))


TOP_Y = course_top(LAYERS - 1)          # -144, top face of the wall
WIN_TOP = course_top(WINDOW_COURSES[-1])  # -96, top face of the upper window course
# The roof reference sits one plate height ABOVE the wall: the deck plate's
# bottom face must land on TOP_Y, so its top face goes at TOP_Y - PLATE.
ROOF_Y = TOP_Y - PLATE

# Brick refs keyed by stud length (from rectangular-parts.json).
BRICK_REF = {4: '3010', 6: '3009'}


# --- helpers ----------------------------------------------------------------
def tile(lo: float, hi: float, pattern):
    """Lay pieces along one axis so their envelopes exactly cover [lo, hi].

    `pattern` is stud counts; it must sum to the span length in studs.
    Returns [(centre, studs), ...]. Order matters -- it is the build order.
    """
    span = hi - lo
    if sum(pattern) * STUD != span:
        raise ValueError(f"pattern {pattern} does not tile [{lo}, {hi}] "
                         f"({span} LDU / {span / STUD:g} studs)")
    out, cursor = [], lo
    for n in pattern:
        out.append((round(cursor + n * STUD / 2.0, 3), n))
        cursor += n * STUD
    return out


def place(pid, ref, colour, at=None, purpose=None, yaw=None, repeat=None):
    """One placement. A bare part number gets `.dat`; module names already
    carry `.ldr` and are left alone."""
    if not ref.startswith('@') and '.' not in ref:
        ref += '.dat'
    entry = dict(id=pid, ref=ref, colour=colour)
    if at is not None:
        entry['at'] = at
    if purpose:
        entry['purpose'] = purpose
    if yaw:
        entry['yaw'] = yaw
    if repeat:
        entry['repeat'] = repeat
    return entry


def section(name, description, steps, anchors=None):
    sec = dict(name=name + '.ldr', description=description, steps=steps)
    if anchors:
        sec['anchors'] = anchors
    return sec


# --- reusable modules -------------------------------------------------------
def door_module():
    """Door 1 x 4 x 6: frame + leaf. Height 144 LDU == LAYERS brick courses."""
    return section('kiosk2-door', 'Glazed entrance door, 4 studs x 6 bricks', [
        # 60596 bounds: x[-40,40] y[-4,144] -> place so its bottom lands on y=0.
        [place('frame', '60596', 16, [0, 0, 0], purpose='door frame, 4 studs wide')],
        # 60623 is drawn offset in x: bounds x[-3,67] against the frame's
        # [-40,40], so shift it -32 to centre the leaf inside the frame.
        [place('leaf', '60623', C_DOOR, [-32, 0, 0], purpose='hinged door leaf')],
    ])


def window_module():
    """Window 1 x 2 x 2 + matching glass. 2 studs wide, 2 courses tall."""
    return section('kiosk2-window', 'Window 1 x 2 x 2 with glazing', [
        [place('frame', '60592', 16, [0, 0, 0], purpose='window frame')],
        [place('glass', '60601', C_GLASS, [0, 0, 0], purpose='window glazing')],
    ])


def roof_module():
    """Flat roof: deck + parapet + chimney.

    Local origin sits on the DECK top face; everything else is offset from it.
    Up is negative, so the parapet (above the deck) is at -PLATE.
    """
    steps = []

    # Deck: two 6x12 plates make the 12x12 square.
    steps.append([
        place('deck-a', '3028', C_ROOF, [0, 0, -60], purpose='rear roof deck plate'),
        place('deck-b', '3028', C_ROOF, [0, 0, 60], purpose='front roof deck plate'),
    ])

    # Parapet: a closed ring of plates. The front/back runs own the corners,
    # so the side runs stop at +/-INNER and the lengths must still tile.
    trim = []
    for run_z, tag in ((Z_BACK, 'back'), (Z_FRONT, 'front')):
        for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
            trim.append(place(f'trim-{tag}-{i}', '3666', C_TRIM,
                              [cx, -PLATE, run_z], purpose=f'{tag} parapet, {n} studs'))
    for run_x, tag in ((X_LEFT, 'left'), (X_RIGHT, 'right')):
        # inner span is 10 studs -> 6 + 4, mirrored per side for a bonded look
        for i, (cz, n) in enumerate(tile(-INNER, INNER, (6, 4) if tag == 'left' else (4, 6))):
            trim.append(place(f'trim-{tag}-{i}', '3666' if n == 6 else '3710', C_TRIM,
                              [run_x, -PLATE, cz], yaw=90,
                              purpose=f'{tag} parapet, {n} studs'))
    steps.append(trim)

    # Chimney: three 2x2 bricks capped with a plate, centred on the rear deck.
    CX, CZ = 60, -60
    steps.append([
        place('chimney', '3003', C_CHIMNEY, [CX, -BRICK, CZ],
              purpose='chimney stack, three bricks high',
              repeat={'count': 3, 'step': [0, -BRICK, 0]}),
        place('chimney-cap', '3022', C_CHIMNEY, [CX, -BRICK * 4, CZ],
              purpose='chimney cap plate'),
    ])
    return section('kiosk2-roof', 'Flat roof deck with parapet ring and chimney',
                   steps, anchors={'base': {'at': [0, 0, 0]}})


# --- main assembly ----------------------------------------------------------
def main_steps():
    steps = []

    # Step 0: base plates, tiled along Z to make a true square.
    steps.append([
        place('base-a', '3028', C_BASE, [0, 0, -60], purpose='rear base plate'),
        place('base-b', '3028', C_BASE, [0, 0, 60], purpose='front base plate'),
    ])

    # Step 1: back wall. Uniform every course -> express as one repeat.
    steps.append([
        place(f'back-{i}', '3009', C_WALL, [cx, -BRICK, Z_BACK],
              purpose=f'back wall column of {n} bricks',
              repeat={'count': LAYERS, 'step': [0, -BRICK, 0]})
        for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6)))
    ])

    # Step 2: side walls. The bond alternates per course, so the tile pattern
    # flips -- this is exactly the kind of arithmetic that should never be typed.
    sides = []
    for c in range(LAYERS):
        for run_x, tag in ((X_LEFT, 'left'), (X_RIGHT, 'right')):
            pattern = (6, 4) if (c + (0 if tag == 'left' else 1)) % 2 == 0 else (4, 6)
            for i, (cz, n) in enumerate(tile(-INNER, INNER, pattern)):
                sides.append(place(
                    f'{tag}-{c}-{i}', BRICK_REF[n], C_WALL,
                    [run_x, course_top(c), cz], yaw=90,
                    purpose=f'{tag} wall course {c}, {n}-stud brick'))
    steps.append(sides)

    # Step 3: front wall. Middle 4 studs stay open for the door; the flanks
    # either carry 4-stud bricks or, on the window courses, two 2-stud windows.
    # door opening takes the middle 4 studs, leaving one 4-stud flank each side
    # (12 - 4) / 2 = 4 studs -> 3010 Brick 1 x 4, or two 2-stud windows.
    front = []
    for c in range(LAYERS):
        if c in WINDOW_COURSES:
            if c != WINDOW_COURSES[0]:
                continue                       # the module spans both courses
            pattern, top = (2, 2), WIN_TOP
        else:
            pattern, top = (4,), course_top(c)
        for lo, hi, tag in ((-HALF, -40, 'l'), (40, HALF, 'r')):
            for i, (cx, n) in enumerate(tile(lo, hi, pattern)):
                if top == WIN_TOP:
                    front.append(place(f'win-{tag}-{i}', 'kiosk2-window.ldr', C_FRAME,
                                       [cx, top, Z_FRONT],
                                       purpose=f'{tag} display window at x={cx}'))
                else:
                    front.append(place(f'front-{tag}-{c}-{i}', BRICK_REF[n], C_WALL,
                                       [cx, top, Z_FRONT],
                                       purpose=f'{tag} front flank course {c}'))
    steps.append(front)

    # Step 4: the door drops into the opening. NOTE: the modules use colour 16
    # internally for their frames, so this reference MUST carry a concrete
    # colour or validation fails with colour.unresolved_current.
    steps.append([
        place('entrance', 'kiosk2-door.ldr', C_FRAME, [0, -BRICK * LAYERS, Z_FRONT],
              purpose='entrance assembly filling the 4-stud opening'),
    ])

    # Step 5: roof sits above the wall.
    steps.append([
        place('roof', 'kiosk2-roof.ldr', C_ROOF, [0, ROOF_Y, 0],
              purpose='roof assembly resting on the wall top face'),
    ])
    return steps


def build() -> dict:
    main = section('kiosk2-main',
                   'Corner coffee kiosk: 12x12 studs, red brick walls with a '
                   'bonded ring, glazed front and a parapeted flat roof',
                   main_steps())
    return dict(version=1, author=AUTHOR,
                sections=[main, door_module(), window_module(), roof_module()])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=Path('output/kiosk_v2.plan.json'))
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    print(f'wrote {args.output.resolve()}')
    print(f'wall top face {TOP_Y:g} LDU, {LAYERS} courses, roof datum {ROOF_Y:g}')


if __name__ == '__main__':
    main()
