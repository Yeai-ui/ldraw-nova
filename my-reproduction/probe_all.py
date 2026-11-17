import json, urllib.request

cfg = json.load(open('/config/models.json'))
tok = cfg['models'][0]['litellm_params']['api_key']
URL = 'https://api-inference.modelscope.cn/v1/chat/completions'
req0 = urllib.request.Request('https://api-inference.modelscope.cn/v1/models', headers={'Authorization': 'Bearer ' + tok})
ids = [m['id'] for m in json.loads(urllib.request.urlopen(req0, timeout=30).read())['data']]

def call(model, payload_extra=None, timeout=40):
    body = json.dumps({'model': model, 'messages': [{'role':'user','content':'hi'}], 'max_tokens': 5, **(payload_extra or {})}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError as e:
        return 'HTTP %d: %s' % (e.code, e.read(120).decode(errors='ignore')[:90])
    except Exception as e:
        return type(e).__name__

alive = []
for i in ids:
    r = call(i)
    tag = 'ALIVE' if r is True else r
    print('%-45s %s' % (i, tag), flush=True)
    if r is True: alive.append(i)
print()
print('真正可用 (%d):' % len(alive))
for a in alive: print('  ', a)
