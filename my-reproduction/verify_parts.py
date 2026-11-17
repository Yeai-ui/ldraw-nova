import subprocess, json

PY = r'.venv\Scripts\python.exe'

PARTS = ['3028', '3009', '3010', '3003', '3022', '3020', '3005',
         '60592', '60601', '60596', '60623', '3068b', '3039', '3460',
         '3666', '3024', '3001', '3007']

for p in PARTS:
    r = subprocess.run([PY, '-m', 'ldraw_tools.cli', 'part', p, '--limit', '1'],
                       capture_output=True, text=True, timeout=300)
    ok = r.returncode == 0
    desc = ''
    if ok:
        try:
            d = json.loads(r.stdout)
            desc = d.get('description') or d.get('title') or str(d)[:80]
        except Exception:
            desc = (r.stdout or '')[:80]
    else:
        desc = (r.stdout or '').strip().splitlines()[-1][:100] if r.stdout else (r.stderr or '')[:100]
    print('%-8s %s  %s' % (p, 'OK  ' if ok else 'FAIL', desc))
