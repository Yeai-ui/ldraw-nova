import json, urllib.request, base64

cfg = json.load(open('/config/models.json'))
tok = cfg['models'][0]['litellm_params']['api_key']
URL = 'https://api-inference.modelscope.cn/v1/chat/completions'
def call(model, payload_extra, timeout=45):
    body = json.dumps({'model': model, 'messages': [{'role':'user','content':'hi'}], 'max_tokens': 10, **payload_extra}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return 'OK ' + r.read(80).decode(errors='ignore')[:60]
    except urllib.error.HTTPError as e:
        return 'HTTP %d %s' % (e.code, e.read(180).decode(errors='ignore')[:120])

tools = [{'type':'function','function':{'name':'brick','description':'place a brick','parameters':{'type':'object','properties':{'x':{'type':'integer'}},'required':['x']}}}]
cands = ['OpenGVLab/InternVL3_5-241B-A28B','PaddlePaddle/ERNIE-4.5-VL-28B-A3B-PT','Shanghai_AI_Laboratory/Intern-S1-mini','stepfun-ai/Step-3.7-Flash']
for c in cands:
    print('%-42s tools: %s' % (c, call(c, {'tools': tools})), flush=True)

png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
img_msg = [{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+png}},{'type':'text','text':'what color?'}]}]
for c in ['OpenGVLab/InternVL3_5-241B-A28B','PaddlePaddle/ERNIE-4.5-VL-28B-A3B-PT']:
    body = json.dumps({'model': c, 'messages': img_msg, 'max_tokens': 15}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        d = json.loads(r.read())
        print('%-42s vision: OK  answer=%s' % (c, d['choices'][0]['message']['content'][:40]), flush=True)
    except urllib.error.HTTPError as e:
        print('%-42s vision: HTTP %d %s' % (c, e.code, e.read(150).decode(errors='ignore')[:100]), flush=True)
