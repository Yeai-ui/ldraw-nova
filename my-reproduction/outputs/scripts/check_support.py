"""Support check for a plan.json: which placements rest on nothing.

A placement is supported when some other placement's TOP FACE equals its
BOTTOM FACE with overlapping X/Z footprint, or when it sits on the ground
plane (bottom face == 0, i.e. on the base plates).

Usage: python output/check_support.py output/noodleshop.plan.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_geom import flatten  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'output/noodleshop.plan.json'
    items = flatten(json.loads(Path(path).read_text(encoding='utf-8')))
    boxes = [(i[0], i[1], i[2]) for i in items]
    loose = []
    for pid, ref, b in boxes:
        x0, x1, y0, y1, z0, z1 = b
        bottom = y1                      # up is negative: bottom = y + height
        if abs(bottom) < 1e-6:           # resting on the ground / base plates
            continue
        held = False
        for opid, oref, ob in boxes:
            if opid == pid:
                continue
            if abs(ob[2] - bottom) > 1e-6:        # other's top == my bottom
                continue
            ox = min(x1, ob[1]) - max(x0, ob[0])
            oz = min(z1, ob[5]) - max(z0, ob[4])
            if ox > 1e-6 and oz > 1e-6:
                held = True
                break
        if not held:
            loose.append((pid, ref, [round(v, 1) for v in b]))
    print(f'unsupported placements: {len(loose)} / {len(boxes)}')
    for pid, ref, b in loose:
        print(f'  FLOATING {pid} [{ref}] bounds={b}')


if __name__ == '__main__':
    main()
