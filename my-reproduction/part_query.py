import subprocess, sys, json

PY = r'.venv\Scripts\python.exe'
ENV = None

QUERIES = [
    ('plate 6 x 12', 1),
    ('brick 1 x 6', 3),
    ('brick 1 x 8', 3),
    ('window 1 x 2 x 2', 4),
    ('window frame', 3),
    ('roof tile 1 x 2', 3),
    ('door 1 x 4', 3),
    ('plate 2 x 6', 2),
    ('tile 2 x 2', 2),
    ('slope 45 2 x 2', 2),
]

for q, limit in QUERIES:
    r = subprocess.run([PY, '-m', 'ldraw_tools.cli', 'search', 'parts', q, '--limit', str(limit)],
                       capture_output=True, text=True, timeout=300)
    print('### %s (limit %d) exit=%s' % (q, limit, r.returncode))
    try:
        data = json.loads(r.stdout)
        for item in data.get('results', []):
            print('   %-16s %s' % (item.get('code'), item.get('description')))
    except Exception:
        print('   RAW:', (r.stdout or '')[:200], (r.stderr or '')[:200])
    print()
