"""Original model: a corner coffee kiosk.

Demonstrates the LDraw Nova method: the generator COMPUTES geometry
(loops, stacking arithmetic, symmetry) instead of hand-writing coordinates.
Run:  python generate_kiosk.py --output output/kiosk.plan.json
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
C_FRAME = 19       # Tan - resolved on the submodel REFERENCE so internal 16s inherit
C_CHIMNEY = 0       # Black

# --- kiosk envelope --------------------------------------------------------
# Footprint 12 x 12 studs = 240 x 240 LDU, centred on the origin.
HALF = 6 * STUD            # 120
WALL_T = 10                # wall centre inset from the edge (half a stud)
Z_BACK = HALF - WALL_T     # 110
Z_FRONT = -Z_BACK
X_LEFT = -Z_BACK
X_RIGHT = Z_BACK

LAYERS = 4                 # four brick courses of wall
TOP_Y = -(PLATE + BRICK * LAYERS)   # -104, top surface of the wall


def place(pid, ref, colour, at=None, purpose=None, **kw):
    """One placement. `ref` may be a bare part number; `.dat` is appended."""
    if not ref.startswith('@') and '.' not in ref:
        ref += '.dat'
    entry = dict(id=pid, ref=ref, colour=colour)
    if at is not None:
        entry['at'] = at
    if purpose:
        entry['purpose'] = purpose
    entry.update(kw)
    return entry


def section(name, description, steps, anchors=None):
    sec = dict(name=name + '.ldr', description=description, steps=steps)
    if anchors:
        sec['anchors'] = anchors
    return sec


def wall_run(prefix, x, z, yaw, colour, layers=LAYERS):
    """Stack `layers` bricks vertically at one plan position."""
    return place(f'{prefix}', '3009', colour, [x, -PLATE, z],
                 purpose=f'wall course stack at ({x},{z})',
                 yaw=yaw, repeat={'count': layers, 'step': [0, -BRICK, 0]})


def build() -> dict:
    # --- 1. Reusable door module ------------------------------------------
    door = section('kiosk-door', 'Glazed entrance door with frame', [
        [place('frame', '60596', 16, [0, 0, 0], purpose='door frame')],
        [place('leaf', '60623', C_DOOR, [-32, 0, 5], purpose='hinged door leaf')],
    ])

    # --- 2. Reusable window module ----------------------------------------
    window = section('kiosk-window', 'Window frame with matching glazing', [
        [place('frame', '60592', 16, [0, 0, 0], purpose='window frame')],
        [place('glass', '60601', C_GLASS, [0, 0, 0], purpose='window glazing')],
    ])

    # --- 3. Roof module ----------------------------------------------------
    roof_steps = [
        # Deck: two 6x12 plates cover the 12x12 footprint.
        [place('deck-l', '3028', C_ROOF, [-60, 0, 0], purpose='left roof deck plate'),
         place('deck-r', '3028', C_ROOF, [60, 0, 0], purpose='right roof deck plate')],
        # Parapet trim: 1x6 plates around the perimeter, one course up.
        [place('trim-back-a', '3666', C_TRIM, [-60, -PLATE, Z_BACK], purpose='rear parapet trim'),
         place('trim-back-b', '3666', C_TRIM, [60, -PLATE, Z_BACK], purpose='rear parapet trim'),
         place('trim-front-a', '3666', C_TRIM, [-60, -PLATE, Z_FRONT], purpose='front parapet trim'),
         place('trim-front-b', '3666', C_TRIM, [60, -PLATE, Z_FRONT], purpose='front parapet trim'),
         place('trim-left-a', '3666', C_TRIM, [X_LEFT, -PLATE, -60], yaw=90, purpose='left parapet trim'),
         place('trim-left-b', '3666', C_TRIM, [X_LEFT, -PLATE, 60], yaw=90, purpose='left parapet trim'),
         place('trim-right-a', '3666', C_TRIM, [X_RIGHT, -PLATE, -60], yaw=90, purpose='right parapet trim'),
         place('trim-right-b', '3666', C_TRIM, [X_RIGHT, -PLATE, 60], yaw=90, purpose='right parapet trim')],
        # Chimney stack on the rear half, capped black.
        [place('chimney', '3003', C_CHIMNEY, [80, -PLATE, 60],
               purpose='chimney stack', repeat={'count': 3, 'step': [0, -BRICK, 0]}),
         place('chimney-cap', '3022', C_CHIMNEY, [80, -PLATE - BRICK * 3, 60],
               purpose='chimney cap')],
    ]
    roof = section('kiosk-roof', 'Flat roof deck with parapet trim and chimney', roof_steps,
                   anchors={'base': {'at': [0, PLATE, 0]}})

    # --- 4. Main assembly --------------------------------------------------
    main_steps = []

    # Step 0: base plates
    main_steps.append([
        place('base-l', '3028', C_BASE, [-60, 0, 0], purpose='left base plate'),
        place('base-r', '3028', C_BASE, [60, 0, 0], purpose='right base plate'),
    ])

    # Step 1: back wall, two runs of four courses
    main_steps.append([
        wall_run('wall-back-l', -60, Z_BACK, 0, 5),
        wall_run('wall-back-r', 60, Z_BACK, 0, 5),
    ])

    # Step 2: side walls (yaw 90 so the 6-stud length runs along Z)
    main_steps.append([
        wall_run('wall-left-f', X_LEFT, -60, 90, 5),
        wall_run('wall-left-b', X_LEFT, 60, 90, 5),
        wall_run('wall-right-f', X_RIGHT, -60, 90, 5),
        wall_run('wall-right-b', X_RIGHT, 60, 90, 5),
    ])

    # Step 3: front wall flanks - leave the middle 4 studs as the doorway
    main_steps.append([
        place('front-l', '3010', 5, [-80, -PLATE, Z_FRONT],
              purpose='left front flank beside the doorway',
              repeat={'count': LAYERS, 'step': [0, -BRICK, 0]}),
        place('front-r', '3010', 5, [80, -PLATE, Z_FRONT],
              purpose='right front flank beside the doorway',
              repeat={'count': LAYERS, 'step': [0, -BRICK, 0]}),
    ])

    # Step 4: door module dropped into the opening, plus two windows above
    main_steps.append([
        # NOTE: the modules use colour 16 internally for their frames, so this
        # reference MUST carry a concrete colour or validation fails with
        # colour.unresolved_current (validation.py:219).
        place('entrance', 'kiosk-door.ldr', C_FRAME, [0, -PLATE, Z_FRONT],
              purpose='entrance assembly in the front opening'),
        place('window-l', 'kiosk-window.ldr', C_FRAME, [-60, -PLATE - BRICK * 2, Z_FRONT],
              purpose='left display window'),
        place('window-r', 'kiosk-window.ldr', C_FRAME, [60, -PLATE - BRICK * 2, Z_FRONT],
              purpose='right display window'),
    ])

    # Step 5: roof sits on the wall top surface
    main_steps.append([
        place('roof', 'kiosk-roof.ldr', C_ROOF, [0, TOP_Y, 0], purpose='roof assembly'),
    ])

    main = section('kiosk-main',
                   'Corner coffee kiosk: 12x12 base, red brick walls, glazed entrance and parapet roof',
                   main_steps)

    return dict(version=1, author=AUTHOR, sections=[main, door, window, roof])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=Path('output/kiosk.plan.json'))
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
