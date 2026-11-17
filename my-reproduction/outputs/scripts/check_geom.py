"""Local geometry pre-check for a plan.json: reports AABB body overlaps with
placement ids, so build errors can be fixed without round-tripping the CLI.

Usage: python output/check_geom.py output/noodleshop.plan.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECT = json.loads((ROOT / 'ldraw_tools/data/rectangular-parts.json').read_text(encoding='utf-8'))['parts']
STUD = 20


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def bounds(ref, at, yaw):
    key = ref[:-4] if ref.endswith('.dat') else ref
    p = RECT.get(key)
    if p is None:
        return None
    xs, zs = p['x_studs'], p['z_studs']
    if yaw % 180 == 90:
        xs, zs = zs, xs
    x, y, z = at
    return (x - xs * STUD / 2.0, x + xs * STUD / 2.0,
            y, y + p['height'],
            z - zs * STUD / 2.0, z + zs * STUD / 2.0)


def flatten(plan):
    sections = {s['name']: s for s in plan['sections']}
    out = []

    def walk(name, offset, yaw, prefix):
        sec = sections[name]
        for step in sec['steps']:
            for pl in step:
                ref = pl['ref']
                at = [pl['at'][i] + offset[i] for i in range(3)] if 'at' in pl else list(offset)
                rep = pl.get('repeat')
                count = rep['count'] if rep else 1
                step_v = rep['step'] if rep else [0, 0, 0]
                for k in range(count):
                    pos = [at[i] + step_v[i] * k for i in range(3)]
                    pid = f'{prefix}{pl["id"]}' + (f'-{k}' if rep else '')
                    if ref.endswith('.ldr'):
                        walk(ref, pos, pl.get('yaw', 0), pid + '/')
                    else:
                        b = bounds(ref, pos, (yaw + pl.get('yaw', 0)) % 360)
                        if b:
                            out.append((pid, ref, b))

    main = plan['sections'][0]['name']
    walk(main, [0, 0, 0], 0, '')
    return out


def main():
    plan = load(sys.argv[1] if len(sys.argv) > 1 else 'output/noodleshop.plan.json')
    items = flatten(plan)
    print(f'checked rectangular placements: {len(items)}')
    bad = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][2], items[j][2]
            ox = min(a[1], b[1]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[2], b[2])
            oz = min(a[5], b[5]) - max(a[4], b[4])
            if ox > 1e-6 and oy > 1e-6 and oz > 1e-6:
                bad += 1
                if bad <= 40:
                    print(f'OVERLAP {min(ox,oy,oz):g}  {items[i][0]} [{items[i][1]}] '
                          f'vs {items[j][0]} [{items[j][1]}]')
    print(f'overlaps: {bad}')


if __name__ == '__main__':
    main()
