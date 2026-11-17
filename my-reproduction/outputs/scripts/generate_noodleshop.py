"""Street-corner noodle shop — plan generator (route B, Windows).

The model is a cyberpunk street corner: a 24 x 24 stud base, a removable
ground-floor noodle shop, a narrow apartment above it, an awning, a warm
sign band, external pipes and a small delivery robot.

Everything is COMPUTED. Conventions encoded once and reused:

  1. `at:[x,Y,z]` places the part's TOP FACE at Y; the body occupies
     [Y, Y+height]. Stacking UP therefore means SUBTRACTING.
  2. Footprints come from ldraw_tools/data/rectangular-parts.json, never
     from the part name (3009 "Brick 1 x 6" is x_studs=6, z_studs=1).
  3. Walls are 1 stud thick and must tile their run with EXACTLY abutting
     envelopes -- the body-overlap check has no tolerance for brick bonds.

Run:  python output/generate_noodleshop.py --output output/noodleshop.plan.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

AUTHOR = "Ye Shuai - LDraw Nova route B self-test"

# --- LDraw constants (LDU) ---------------------------------------------------
STUD = 20
PLATE = 8
BRICK = 24
DOOR_H = 144          # 60596 door frame: 6 brick courses
WIN_H = 48            # 60592 window: 2 brick courses

# --- palette -----------------------------------------------------------------
C_BASE = 72           # Dark_BluishGray
C_WALK = 71           # Light_BluishGray  (street)
C_SHOP = 378          # Sand_Green        (shop walls)
C_UPPER = 72          # Dark_BluishGray   (apartment walls)
C_FLOOR = 71          # Light_BluishGray
C_ROOF = 72           # Dark_BluishGray
C_TRIM = 378          # Sand_Green
C_SIGN = 225          # Warm_Yellowish_Orange (warm light)
C_LAMP = 46           # Trans_Yellow      (lanterns)
C_FRAME = 71          # Light_BluishGray  (door/window frames)
C_DOOR = 308          # Dark_Brown
C_GLASS = 47          # Trans_Clear
C_PLANT = 378         # Sand_Green
C_PIPE = 72           # Dark_BluishGray

# --- envelope ---------------------------------------------------------------
HALF_BASE = 240       # 24 studs -> half span
HALF = 120            # shop is 12 x 12 studs
WALL_OFF = 110        # centreline of a 1-stud wall
INNER = 100           # side runs stop here (corners belong to front/back)

# vertical datums (top faces; up is negative)
BASE_TOP = 0
FLOOR_TOP = -PLATE                 # -8, ground floor walking surface
GROUND_COURSES = 8
GROUND_TOP = FLOOR_TOP - BRICK * GROUND_COURSES          # -200
GROUND_ROOF_Y = GROUND_TOP - PLATE                       # -208
UP_FLOOR_Y = GROUND_ROOF_Y - PLATE                       # -216
UP_COURSES = 8
UP_TOP = UP_FLOOR_Y - BRICK * UP_COURSES                 # -408
UP_ROOF_Y = UP_TOP - PLATE                               # -416

STREET_Z0, STREET_Z1 = 120, 240    # street strip in front of the shop
ROBOT = (160, 180)

BRICK_REF = {1: '3005', 2: '3004', 3: '3622', 4: '3010', 6: '3009', 8: '3008'}
PLATE1_REF = {1: '3024', 2: '3023b', 3: '3623', 4: '3710', 6: '3666', 8: '3460'}


def gtop(i: int) -> float:
    """Top face of ground-floor brick course i (0 = bottom)."""
    return FLOOR_TOP - BRICK * (i + 1)


def utop(i: int) -> float:
    """Top face of apartment brick course i."""
    return UP_FLOOR_Y - BRICK * (i + 1)


# --- helpers ----------------------------------------------------------------
def tile(lo: float, hi: float, pattern):
    """Lay pieces along one axis so envelopes exactly cover [lo, hi].

    `pattern` holds stud counts and must sum to the span. Returns
    [(centre, studs), ...] in build order.
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


def plate_field(x0, x1, z0, z1, y, colour, tag, pw=4, ph=2):
    """Fill a rectangle with 2 x 4 plates (80 x 40 LDU)."""
    ref = {4: '3020'}[pw]
    cols = round((x1 - x0) / (pw * STUD))
    rows = round((z1 - z0) / (ph * STUD))
    if cols * pw * STUD != (x1 - x0) or rows * ph * STUD != (z1 - z0):
        raise ValueError(f"plate_field {tag}: {x0},{x1},{z0},{z1} not tileable")
    out = []
    for r in range(rows):
        for c in range(cols):
            cx = x0 + (c * pw + pw / 2.0) * STUD
            cz = z0 + (r * ph + ph / 2.0) * STUD
            out.append(place(f'{tag}-{r}-{c}', ref, colour,
                             [round(cx, 3), y, round(cz, 3)],
                             purpose=f'{tag} plate row {r} col {c}'))
    return out


def place(pid, ref, colour, at=None, purpose=None, yaw=None, repeat=None):
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
    return section('noodle-door', 'Glazed shop entrance, 4 studs x 6 courses', [
        [place('frame', '60596', C_FRAME, [0, 0, 0], purpose='door frame'),
         place('leaf', '60623', C_DOOR, [-32, 0, 0], purpose='hinged door leaf')],
    ])


def window_module():
    return section('noodle-window', 'Window 1 x 2 x 2 with glazing', [
        [place('frame', '60592', C_FRAME, [0, 0, 0], purpose='window frame'),
         place('glass', '60601', C_GLASS, [0, 0, 0], purpose='window glazing')],
    ])


# --- ground floor (removable module) ----------------------------------------
def ground_steps():
    steps = []

    # floor deck: 12 x 12 studs of 2 x 4 plates
    steps.append(plate_field(-HALF, HALF, -HALF, HALF, FLOOR_TOP, C_FLOOR, 'floor'))

    # back wall: uniform every course
    back = []
    for c in range(GROUND_COURSES):
        for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
            back.append(place(f'back-{c}-{i}', BRICK_REF[n], C_SHOP,
                              [cx, gtop(c), -WALL_OFF],
                              purpose=f'back wall course {c}, {n}-stud brick'))
    steps.append(back)

    # front wall: door opening takes the middle 4 studs for courses 0-5
    front = []
    for c in range(GROUND_COURSES):
        if c in (2, 3):
            if c != 2:
                continue                     # window modules span both courses
            for i, (cx, n) in enumerate(tile(-HALF, -40, (2, 2))):
                front.append(place(f'win-l-{i}', 'noodle-window.ldr', C_FRAME,
                                   [cx, gtop(3), WALL_OFF],
                                   purpose=f'left shopfront window at x={cx}'))
            for i, (cx, n) in enumerate(tile(40, HALF, (2, 2))):
                front.append(place(f'win-r-{i}', 'noodle-window.ldr', C_FRAME,
                                   [cx, gtop(3), WALL_OFF],
                                   purpose=f'right shopfront window at x={cx}'))
        elif c < 6:
            for lo, hi, tag in ((-HALF, -40, 'l'), (40, HALF, 'r')):
                for i, (cx, n) in enumerate(tile(lo, hi, (4,))):
                    front.append(place(f'front-{tag}-{c}-{i}', BRICK_REF[n], C_SHOP,
                                       [cx, gtop(c), WALL_OFF],
                                       purpose=f'{tag} shopfront flank course {c}'))
        else:                                # lintel over the entrance
            for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
                front.append(place(f'lintel-{c}-{i}', BRICK_REF[n], C_SHOP,
                                   [cx, gtop(c), WALL_OFF],
                                   purpose=f'lintel course {c}, {n}-stud brick'))
    steps.append(front)

    # entrance drops into the opening
    steps.append([
        place('entrance', 'noodle-door.ldr', C_FRAME,
              [0, FLOOR_TOP - DOOR_H, WALL_OFF],
              purpose='shop entrance filling the 4-stud opening'),
    ])

    # side walls: bond alternates per course
    sides = []
    for c in range(GROUND_COURSES):
        for run_x, tag in ((-WALL_OFF, 'left'), (WALL_OFF, 'right')):
            pattern = (6, 4) if (c + (0 if tag == 'left' else 1)) % 2 == 0 else (4, 6)
            for i, (cz, n) in enumerate(tile(-INNER, INNER, pattern)):
                sides.append(place(f'{tag}-{c}-{i}', BRICK_REF[n], C_SHOP,
                                   [run_x, gtop(c), cz], yaw=90,
                                   purpose=f'{tag} wall course {c}, {n}-stud brick'))
    steps.append(sides)

    # --- interior -----------------------------------------------------------
    # counter along the back, two courses plus a plate top
    counter = []
    for c, y in enumerate((gtop(0), gtop(1))):
        for i, (cx, n) in enumerate(tile(-INNER, INNER, (6, 4))):
            counter.append(place(f'counter-{c}-{i}', BRICK_REF[n], C_FLOOR,
                                 [cx, y, -90],
                                 purpose=f'counter course {c}, {n}-stud brick'))
    for i, (cx, n) in enumerate(tile(-INNER, INNER, (6, 4))):
        counter.append(place(f'counter-top-{i}', PLATE1_REF[n], C_TRIM,
                             [cx, gtop(1) - PLATE, -90],
                             purpose='counter worktop'))
    steps.append(counter)

    # stove: 2 x 2 brick in the band z -80..-40, clear of the counter row
    steps.append([
        place('stove', '3003', C_BASE, [60, gtop(0), -60], purpose='stove body'),
        place('stove-top', '3022', C_BASE, [60, gtop(0) - PLATE, -60],
              purpose='stove hot plate'),
        place('pan-a', '3070b', C_BASE, [50, gtop(0) - 2 * PLATE, -50],
              purpose='wok'),
        place('pan-b', '3070b', C_BASE, [70, gtop(0) - 2 * PLATE, -50],
              purpose='stock pot'),
    ])

    # rug: a row of four 2 x 2 tiles across z -40..0
    steps.append([
        place(f'rug-{i}', '3068b', C_SHOP, [rx, FLOOR_TOP - PLATE, -20],
              purpose='interior floor tile')
        for i, rx in enumerate((-60, -20, 20, 60))
    ])

    # two tables: 2 x 2 brick with a 2 x 2 tiled top, in the band z 0..40
    tables = []
    for i, tx in enumerate((-40, 40)):
        tables.append(place(f'table-{i}-leg', '3003', C_UPPER, [tx, gtop(0), 20],
                            purpose=f'table {i} base'))
        tables.append(place(f'table-{i}-top', '3068b', C_TRIM,
                            [tx, gtop(0) - PLATE, 20], purpose=f'table {i} top'))
    steps.append(tables)

    # four stools: 1 x 1 brick plus a tiled seat, in the band z 50..70
    stools = []
    for i, sx in enumerate((-50, -30, 30, 50)):
        stools.append(place(f'stool-{i}-leg', '3005', C_UPPER, [sx, gtop(0), 60],
                            purpose=f'stool {i} leg'))
        stools.append(place(f'stool-{i}-seat', '3070b', C_SIGN,
                            [sx, gtop(0) - PLATE, 60], purpose=f'stool {i} seat'))
    steps.append(stools)

    # roof deck over the shop
    steps.append(plate_field(-HALF, HALF, -HALF, HALF, GROUND_ROOF_Y, C_ROOF, 'groof'))

    return steps


# --- narrow apartment above -------------------------------------------------
def upper_steps():
    steps = []
    AZ0, AZ1 = -HALF, 0                # 12 x 6 studs, sitting at the rear

    steps.append(plate_field(-HALF, HALF, AZ0, AZ1, UP_FLOOR_Y, C_FLOOR, 'ufloor'))

    back = []
    for c in range(UP_COURSES):
        for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
            back.append(place(f'uback-{c}-{i}', BRICK_REF[n], C_UPPER,
                              [cx, utop(c), -WALL_OFF],
                              purpose=f'apartment back wall course {c}'))
    steps.append(back)

    # Two window bands, courses 2-3 and 5-6. A 60592 frame is TWO courses
    # tall, so its piers must be two bricks as well: a single pier brick
    # leaves the lower course open. Windows sit symmetric at the ends.
    front = []
    for c in range(UP_COURSES):
        if c in (2, 3, 5, 6):
            if c not in (2, 5):
                continue
            for i, (cx, n) in enumerate(tile(-HALF, HALF, (2, 4, 4, 2))):
                if n == 2:
                    front.append(place(f'uwin-{c}-{i}', 'noodle-window.ldr', C_FRAME,
                                       [cx, utop(c + 1), -10],
                                       purpose=f'apartment window, courses {c}-{c + 1}'))
                else:
                    for k in (0, 1):
                        front.append(place(f'uwall-w-{c}-{i}-{k}', BRICK_REF[n], C_UPPER,
                                           [cx, utop(c + k), -10],
                                           purpose=f'apartment front pier, course {c + k}'))
        else:
            for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
                front.append(place(f'ufront-{c}-{i}', BRICK_REF[n], C_UPPER,
                                   [cx, utop(c), -10],
                                   purpose=f'apartment front wall course {c}'))
    steps.append(front)

    sides = []
    for c in range(UP_COURSES):
        for run_x, tag in ((-WALL_OFF, 'uleft'), (WALL_OFF, 'uright')):
            pattern = (2, 2) if (c + (0 if tag == 'uleft' else 1)) % 2 == 0 else (4,)
            for i, (cz, n) in enumerate(tile(AZ0 + STUD, AZ1 - STUD, pattern)):
                sides.append(place(f'{tag}-{c}-{i}', BRICK_REF[n], C_UPPER,
                                   [run_x, utop(c), cz], yaw=90,
                                   purpose=f'apartment {tag} course {c}'))
    steps.append(sides)

    # Two internal pillars. The roof deck spans four studs of open space
    # between the front and back walls; without them the middle plates are
    # carried by nothing. Each pillar is eight 2 x 2 bricks and its top face
    # lands exactly on the wall tops, so the roof deck rests on it.
    pillars = []
    for i, px in enumerate((-40, 40)):
        for c in range(UP_COURSES):
            pillars.append(place(f'upillar-{i}-{c}', '3003', C_UPPER,
                                 [px, utop(c), -60],
                                 purpose=f'apartment internal pillar, course {c}'))
    steps.append(pillars)

    steps.append(plate_field(-HALF, HALF, AZ0, AZ1, UP_ROOF_Y, C_ROOF, 'uroof'))

    # Eaves: one plate course ABOVE the roof deck, offset one stud outward.
    # Each eave plate keeps a one-stud strip over the roof so the roof's
    # studs actually engage it; the outer stud is the overhang. The four
    # strips meet at the corners without overlapping.
    EAVE_Y = UP_ROOF_Y - PLATE
    eaves = []
    for tag, ez in (('front', 0), ('back', -120)):
        for i, (cx, n) in enumerate(tile(-100, 100, (4, 4, 2))):
            eaves.append(place(f'ueave-{tag}-{i}', {4: '3020', 2: '3022'}[n], C_TRIM,
                               [cx, EAVE_Y, ez],
                               purpose=f'apartment eave, {tag} overhang'))
    for tag, ex in (('left', -120), ('right', 120)):
        for i, (cz, n) in enumerate(tile(-140, 20, (4, 4))):
            eaves.append(place(f'ueave-{tag}-{i}', '3020', C_TRIM,
                               [ex, EAVE_Y, cz], yaw=90,
                               purpose=f'apartment eave, {tag} overhang'))
    steps.append(eaves)

    # roof details: two planters and a vent stack, kept clear of the eaves
    steps.append([
        place('planter-a', '3003', C_UPPER, [-60, UP_ROOF_Y - BRICK, -70],
              purpose='roof planter'),
        place('planter-b', '3003', C_UPPER, [60, UP_ROOF_Y - BRICK, -70],
              purpose='roof planter'),
        place('vent', '3005', C_PIPE, [0, UP_ROOF_Y - BRICK, -60],
              purpose='roof vent stack, three bricks',
              repeat={'count': 3, 'step': [0, -BRICK, 0]}),
    ])
    steps.append([
        place(f'plant-{i}', '3005', C_PLANT, [px, UP_ROOF_Y - 2 * BRICK, -70],
              purpose='roof planting')
        for i, px in enumerate((-70, -50, 50, 70))
    ])
    steps.append([
        place(f'topiary-{i}', '3005', C_PLANT, [px, UP_ROOF_Y - 3 * BRICK, -60],
              purpose='roof topiary, second tier')
        for i, px in enumerate((-60, 60))
    ])
    return steps


# --- main assembly ----------------------------------------------------------
def main_steps():
    steps = []

    # base: 24 x 24 studs, four rows of 6 x 8 plates
    base = []
    for r, cz in enumerate((-180, -60, 60, 180)):
        for c, cx in enumerate((-160, 0, 160)):
            base.append(place(f'base-{r}-{c}', '3036', C_BASE, [cx, BASE_TOP, cz],
                              purpose=f'base plate row {r} col {c}'))
    steps.append(base)

    # street strip in front of the shop
    steps.append(plate_field(-HALF_BASE, HALF_BASE, STREET_Z0, STREET_Z1,
                             -PLATE, C_WALK, 'street'))

    # Awning: a canopy that SITS ON THE DOOR HEAD, not across the doorway.
    # Door top face is FLOOR_TOP - DOOR_H (-152); a plate resting on it has its
    # top face one plate higher (-160). It projects two studs out from the wall.
    AWNING_Y = FLOOR_TOP - DOOR_H - PLATE
    awning = [
        place(f'awning-{r}-{c}', '3666', C_TRIM, [cx, AWNING_Y, pz],
              purpose='awning panel above the entrance')
        for r, pz in enumerate((130, 150))
        for c, cx in enumerate((-60, 60))
    ]
    # Eight posts in two rows carry the canopy: one row under each plate row,
    # so neither row reads as a floating slab. The inner row flanks the doorway.
    posts = []
    for r, pz in enumerate((130, 150)):
        for i, px in enumerate((-110, -70, 70, 110)):
            posts.append(place(f'post-{r}-{i}', '3005', C_BASE,
                               [px, -PLATE - BRICK, pz],
                               purpose='arcade post under the awning, six bricks',
                               repeat={'count': 6, 'step': [0, -BRICK, 0]}))
    # Step order below is assembly order: every group also becomes one `0 STEP`
    # marker for the build video, so it has to read bottom-up with structure
    # before decoration -- posts rise off the street, the floors land on the
    # base, and only then does the awning sit on the door head and carry the
    # sign box on top of itself.
    steps.append(posts)

    # the two building modules
    steps.append([
        place('ground', 'noodle-ground.ldr', C_BASE, [0, 0, 0],
              purpose='removable ground floor: shop shell and interior'),
        place('upper', 'noodle-upper.ldr', C_UPPER, [0, 0, 0],
              purpose='narrow apartment above the shop'),
    ])
    steps.append(awning)

    # sign box standing on the canopy + lanterns hanging beneath the entrance
    steps.append([
        place(f'sign-{i}', BRICK_REF[6], C_SIGN,
              [cx, AWNING_Y - BRICK, 130],
              purpose='illuminated shop sign box on the awning')
        for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6)))
    ])
    steps.append([
        place(f'lamp-{i}', '3005', C_LAMP, [lx, gtop(5), 130],
              purpose='hanging lantern under the awning')
        for i, lx in enumerate((-20, 20))
    ])

    # external pipe runs down both flanks
    pipes = []
    for side, px in (('l', -130), ('r', 130)):
        for i, pz in enumerate((-90, -10, 70)):
            pipes.append(place(f'pipe-{side}-{i}', '3005', C_PIPE, [px, -BRICK, pz],
                               purpose='external pipe run, six bricks',
                               repeat={'count': 6, 'step': [0, -BRICK, 0]}))
    steps.append(pipes)

    # terrace railing around the exposed shop roof (front half)
    railing = []
    for i, (cx, n) in enumerate(tile(-HALF, HALF, (6, 6))):
        railing.append(place(f'rail-f-{i}', BRICK_REF[n], C_ROOF,
                             [cx, GROUND_ROOF_Y - BRICK, WALL_OFF],
                             purpose='terrace railing, front'))
    for run_x, tag in ((-WALL_OFF, 'l'), (WALL_OFF, 'r')):
        for i, (cz, n) in enumerate(tile(0, INNER, (3, 2))):
            railing.append(place(f'rail-{tag}-{i}', BRICK_REF[n], C_ROOF,
                                 [run_x, GROUND_ROOF_Y - BRICK, cz], yaw=90,
                                 purpose='terrace railing, side'))
    steps.append(railing)

    # street lamp on the pavement
    steps.append([
        place('lamp-post', '3005', C_BASE, [-180, -PLATE - BRICK, 200],
              purpose='street lamp post, three bricks',
              repeat={'count': 3, 'step': [0, -BRICK, 0]}),
        place('lamp-head', '3005', C_LAMP, [-180, -PLATE - 4 * BRICK, 200],
              purpose='street lamp head'),
    ])

    # crates stacked on the pavement
    steps.append([
        place(f'crate-{i}', '3003', C_TRIM, [cx, -PLATE - BRICK, 200],
              purpose='delivery crate')
        for i, cx in enumerate((-60, -20, 20, 60))
    ])

    # delivery robot on the street
    rx, rz = ROBOT
    steps.append([
        place('robot-base', '3022', C_WALK, [rx, -2 * PLATE, rz],
              purpose='delivery robot chassis'),
        place('robot-body', '3003', C_SHOP, [rx, -2 * PLATE - BRICK, rz],
              purpose='delivery robot body'),
        place('robot-head', '3005', C_LAMP, [rx, -2 * PLATE - 2 * BRICK, rz],
              purpose='delivery robot sensor head'),
        place('robot-arm-l', '3004', C_WALK, [rx - 40, -2 * PLATE - BRICK, rz],
              purpose='delivery robot arm'),
        place('robot-arm-r', '3004', C_WALK, [rx + 40, -2 * PLATE - BRICK, rz],
              purpose='delivery robot arm'),
    ])
    return steps


MAX_PER_STEP = 5        # parts per assembly step; 315 entries -> 79 steps


def regroup_steps(steps, per_step=MAX_PER_STEP):
    """Split coarse building groups into instruction-sized assembly steps.

    The builder turns every plan step into one `0 STEP` marker, and LeoCAD
    renders cumulative frames from those markers, so plan step order IS
    assembly order. The coarse groups already run bottom-up with structure
    before decoration, so we only cut inside a group and never merge across
    its boundary -- merging would scramble that order.
    """
    out = []
    for group in steps:
        for start in range(0, len(group), per_step):
            out.append(group[start:start + per_step])
    return out


def build(per_step: int = MAX_PER_STEP) -> dict:
    main = section('noodle-main',
                   'Cyberpunk street corner: 24 x 24 stud base, removable '
                   'ground-floor noodle shop with glazed shopfront and awning, '
                   'narrow apartment above, sign band, pipe runs and a '
                   'delivery robot',
                   regroup_steps(main_steps(), per_step))
    ground = section('noodle-ground',
                     'Removable ground floor: 12 x 12 stud shop shell, '
                     'sand green walls, glazed front, counter, stove, two '
                     'tables, four stools and a roof deck',
                     regroup_steps(ground_steps(), per_step),
                     anchors={'base': {'at': [0, 0, 0]}})
    upper = section('noodle-upper',
                    'Narrow apartment: 12 x 6 studs, eight courses, two '
                    'window bands of two glazed windows, internal pillars '
                    'carrying the roof, eaves and planters with a vent stack',
                    regroup_steps(upper_steps(), per_step),
                    anchors={'base': {'at': [0, 0, 0]}})
    return dict(version=1, author=AUTHOR,
                sections=[main, ground, upper, door_module(), window_module()])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=Path('output/noodleshop.plan.json'))
    ap.add_argument('--per-step', type=int, default=MAX_PER_STEP,
                    help='parts per assembly step (default: %(default)s)')
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = build(per_step=args.per_step)
    args.output.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    n = sum(len(step) for sec in data['sections'] for step in sec['steps'])
    k = sum(len(sec['steps']) for sec in data['sections'])
    print(f'wrote {args.output.resolve()}')
    print(f'placements: {n}   sections: {len(data["sections"])}')
    print(f'instruction steps: {k}')
    print(f'ground top {GROUND_TOP:g}, apartment top {UP_TOP:g}')


if __name__ == '__main__':
    main()
