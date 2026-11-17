"""Turn a mesh into a brick-by-brick LDraw model.

Runs inside Blender: it imports the mesh (whatever a CAD tool exports),
scales it either to a requested number of studs or to a real-world size,
samples the solid on a stud-sized grid, and covers each layer with ordinary
rectangular bricks. Every layer ends on a ``0 STEP`` marker, which is exactly
what the existing assembly-video pipeline consumes.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import mathutils
from mathutils import Matrix, Vector

# One stud is 20 LDU across and a brick stands 24 LDU tall, so the sampling
# grid is deliberately finer horizontally than it is vertically.
STUD = 20
BRICK = 24

# Rectangular bricks only, keyed (length along x, width along z).
PIECES = {(4, 2): "3001", (3, 2): "3002", (2, 2): "3003",
          (4, 1): "3010", (3, 1): "3622", (2, 1): "3004", (1, 1): "3005"}
ORDER = [(4, 2), (3, 2), (2, 2), (4, 1), (3, 1), (2, 1), (1, 1)]

AXIS = Vector((1.0, 0.0, 0.0))
EPSILON = 1e-4


def blender_args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


IMPORTERS = {".glb": "import_scene.gltf", ".gltf": "import_scene.gltf",
             ".obj": "import_scene.obj", ".stl": "wm.stl_import"}


def import_mesh(path):
    """Load whatever format the upstream tool produced."""
    operator = IMPORTERS.get(path.suffix.lower())
    if operator is None:
        raise SystemExit(f"unsupported mesh format: {path.suffix}")
    module, _, name = operator.partition(".")
    getattr(getattr(bpy.ops, module), name)(filepath=str(path))


def inside_mesh(tree, point, x_limit):
    """Odd number of crossings to the outside means the point is enclosed."""
    origin = point.copy()
    crossings = 0
    while origin.x < x_limit and crossings < 200:
        hit = tree.ray_cast(origin, AXIS)
        if hit[0] is None:
            break
        crossings += 1
        origin = hit[0] + Vector((EPSILON, 0.0, 0.0))
    return crossings % 2 == 1


def cover_layer(grid, wide, deep, reverse):
    """Greedily tile one layer's occupied cells with the largest brick that fits.

    Odd layers are scanned from the far corner so their seams do not line up
    with the layer below -- the brick equivalent of a running bond.
    """
    free = [row[:] for row in grid]
    placed = []
    rows = range(wide - 1, -1, -1) if reverse else range(wide)
    cols = range(deep - 1, -1, -1) if reverse else range(deep)

    for i in rows:
        for j in cols:
            if not free[i][j]:
                continue
            for length, width in ORDER:
                start_i = i - length + 1 if reverse else i
                start_j = j - width + 1 if reverse else j
                if start_i < 0 or start_j < 0:
                    continue
                if start_i + length > wide or start_j + width > deep:
                    continue
                # A generator would be exhausted by the first pass, leaving the
                # cells unclaimed so later bricks would overlap this one.
                cells = [(start_i + a, start_j + b)
                         for a in range(length) for b in range(width)]
                if not all(free[a][b] for a, b in cells):
                    continue
                for a, b in cells:
                    free[a][b] = False
                placed.append((start_i, start_j, length, width))
                break
    return placed


# Column spacing and how far a brick may overhang the support beneath it.
# Real bricks cantilever a stud or two, which is what keeps a sparse pillar
# layout standing; "fill" ignores overhang and packs the cavity solid.
SUPPORT_MODES = {"hidden": (5, 3), "mixed": (4, 2), "fill": (1, 0)}

# Past this many layers a single-stud column is too slender to hold anything,
# so it is doubled to 2x2 instead.
THICK_COLUMN = 8


def block_free(plane, i, j, size, wide, deep):
    if i + size > wide or j + size > deep:
        return False
    return not any(plane[i + a][j + b]
                   for a in range(size) for b in range(size))


def supported_below(occupancy, k, i, j, wide, deep, cantilever):
    """True when something solid sits close enough under this cell.

    A brick resting one or two studs out over the edge of the layer below is a
    normal overhang, so the column check searches a small neighbourhood rather
    than the cell directly underneath.
    """
    for di in range(-cantilever, cantilever + 1):
        for dj in range(-cantilever, cantilever + 1):
            if abs(di) + abs(dj) > cantilever:
                continue
            ii, jj = i + di, j + dj
            if 0 <= ii < wide and 0 <= jj < deep and occupancy[k - 1][ii][jj]:
                return True
    return False


def plan_supports(occupancy, layers, wide, deep, mode):
    """Cells to fill underneath so that nothing is left floating.

    Only cells with nothing -- not even an overhang -- under them need a
    column, and only sampled anchors get one. The stride between anchors is
    what separates the modes: wide means a clean open underside, one means the
    cavity is packed solid.
    """
    stride, cantilever = SUPPORT_MODES[mode]
    columns = {}
    for k in range(1, layers):
        floating = [(i, j) for i in range(wide) for j in range(deep)
                    if occupancy[k][i][j]
                    and not supported_below(occupancy, k, i, j,
                                            wide, deep, cantilever)]
        anchors = [(i, j) for i, j in floating
                   if i % stride == 0 and j % stride == 0]
        if floating and not anchors:
            anchors = [floating[0]]
        for i, j in anchors:
            height = 0
            probe = k - 1
            while probe >= 0 and not occupancy[probe][i][j]:
                height += 1
                probe -= 1
            if height == 0:
                continue
            thick = mode == "mixed" and height >= THICK_COLUMN
            for level in range(k - 1, k - 1 - height, -1):
                if thick and block_free(occupancy[level], i, j, 2, wide, deep):
                    for a in range(2):
                        for b in range(2):
                            occupancy[level][i + a][j + b] = True
                    columns.setdefault(level, []).append((i, j, 2))
                else:
                    occupancy[level][i][j] = True
                    columns.setdefault(level, []).append((i, j, 1))
    return columns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", "--glb", default="output/assets/part3d/model.glb",
                    help="input mesh: .glb/.gltf/.obj/.stl")
    ap.add_argument("--out", default="output/part-lego/part.ldr")
    ap.add_argument("--studs", type=int, default=12,
                    help="bricks across the longest side of the part")
    ap.add_argument("--mm", type=float, default=0.0,
                    help="real length of the longest side in millimetres; "
                         "given this, resolution is derived rather than guessed")
    ap.add_argument("--stud-mm", type=float, default=8.0,
                    help="real width of one stud, used alongside --mm")
    ap.add_argument("--colour", default="70",
                    help="LDraw colour code (70 = reddish brown)")
    ap.add_argument("--support", choices=("none", "hidden", "mixed", "fill"),
                    default="mixed",
                    help="hidden: sparse thin pillars; fill: pack the cavity "
                         "solid; mixed: sparse pillars, thickened when tall")
    args = ap.parse_args(blender_args())

    source = Path(args.mesh)
    if not source.is_absolute():
        source = Path.cwd() / source
    out = Path(args.out)
    if not out.is_absolute():
        out = Path.cwd() / out

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_mesh(source)
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    print(f"DBG imported polygons={len(mesh.data.polygons)}")

    # Mesh exports carry no units, so a real-world length is the honest way to
    # settle how coarse the brick model should be.
    studs = args.studs
    if args.mm > 0:
        studs = max(1, round(args.mm / args.stud_mm))
    print(f"DBG resolution = {studs} studs ({source.name})")

    longest = max(mesh.dimensions)
    mesh.scale = (studs * STUD / longest,) * 3
    bpy.context.view_layer.update()

    # BVHTree.FromObject samples the mesh data as stored, ignoring the object's
    # world transform, so bake scale and the importer's rotation into vertices.
    mesh.data.transform(mesh.matrix_world)
    mesh.matrix_world = Matrix()
    bpy.context.view_layer.update()

    corners = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
    low = [min(c[a] for c in corners) for a in range(3)]
    high = [max(c[a] for c in corners) for a in range(3)]
    print("DBG size in LDU =", tuple(round(high[a] - low[a], 1) for a in range(3)))

    deps = bpy.context.evaluated_depsgraph_get()
    tree = mathutils.bvhtree.BVHTree.FromObject(mesh, deps)

    wide = max(1, math.ceil((high[0] - low[0]) / STUD))
    deep = max(1, math.ceil((high[1] - low[1]) / STUD))
    layers = max(1, math.ceil((high[2] - low[2]) / BRICK))
    print(f"DBG grid = {wide} x {deep} cells, {layers} layers")

    solid = []
    for k in range(layers):
        z = low[2] + (k + 0.5) * BRICK
        plane = []
        for i in range(wide):
            x = low[0] + (i + 0.5) * STUD
            row = []
            for j in range(deep):
                y = low[1] + (j + 0.5) * STUD
                row.append(inside_mesh(tree, Vector((x, y, z)), high[0] + STUD))
            plane.append(row)
        solid.append(plane)

    filled = sum(sum(sum(row) for row in plane) for plane in solid)
    print(f"DBG solid cells = {filled} of {wide * deep * layers}")

    # Blender is Z-up; LDraw builds upward along -Y. Rotating rather than
    # mirroring keeps the part's handedness intact.
    centre_x = (low[0] + high[0]) / 2
    centre_y = (low[1] + high[1]) / 2

    # The pipeline only accepts MPD: a main 0 FILE block first, its Name:
    # header matching it, and 0 NOFILE to close the file.
    name = out.name
    lines = [f"0 FILE {name}", f"0 Name: {name}",
             "0 Author: ldraw-nova mesh2ldraw (image-to-3D)"]
    # Tile every layer before writing anything: supports can only be planned
    # once each layer's footprint is known.
    tiled = [cover_layer(solid[k], wide, deep, reverse=bool(k % 2))
             for k in range(layers)]
    occupancy = [[[False] * deep for _ in range(wide)] for _ in range(layers)]
    for k, plane in enumerate(tiled):
        for start_i, start_j, length, width in plane:
            for a in range(length):
                for b in range(width):
                    occupancy[k][start_i + a][start_j + b] = True

    supports = {}
    if args.support != "none":
        supports = plan_supports(occupancy, layers, wide, deep, args.support)
        print(f"DBG support bricks = {sum(len(v) for v in supports.values())}")

    histogram = {}
    total = 0
    for k in range(layers):
        for start_i, start_j, length, width in tiled[k]:
            part = PIECES[(length, width)]
            x = low[0] + (start_i + length / 2) * STUD - centre_x
            z = low[1] + (start_j + width / 2) * STUD - centre_y
            lines.append(f"1 {args.colour} {x:.2f} {-k * BRICK:.2f} {z:.2f} "
                         f"1 0 0 0 1 0 0 0 1 {part}.dat")
            histogram[part] = histogram.get(part, 0) + 1
            total += 1
        # Columns come after the layer's own bricks so the steps read bottom-up.
        for i, j, size in supports.get(k, []):
            part = "3003" if size == 2 else "3005"
            x = low[0] + (i + size / 2) * STUD - centre_x
            z = low[1] + (j + size / 2) * STUD - centre_y
            lines.append(f"1 {args.colour} {x:.2f} {-k * BRICK:.2f} {z:.2f} "
                         f"1 0 0 0 1 0 0 0 1 {part}.dat")
            histogram[part] = histogram.get(part, 0) + 1
            total += 1
        if k < layers - 1:
            lines.append("0 STEP")
    lines.append("0 NOFILE")

    out.parent.mkdir(parents=True, exist_ok=True)
    # Plain \n, not \r\n: Path.write_text already translates newlines on
    # Windows, and feeding it CRLF produces a blank line after every row.
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"DBG bricks = {total}")
    print("DBG pieces =", dict(sorted(histogram.items())))
    print(f"DBG wrote {out}")


main()
