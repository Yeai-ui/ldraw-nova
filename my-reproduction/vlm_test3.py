import json, urllib.request

cfg = json.load(open('/config/models.json'))
tok = cfg['models'][0]['litellm_params']['api_key']
URL = 'https://api-inference.modelscope.cn/v1/chat/completions'

tools = [{'type':'function','function':{'name':'place_brick','description':'place a brick at coords','parameters':{'type':'object','properties':{'x':{'type':'integer'},'colour':{'type':'string'}},'required':['x']}}}]
for c in ['Shanghai_AI_Laboratory/Intern-S2-Preview','ZhipuAI/GLM-5.2','Qwen/Qwen3.5-397B-A17B','Qwen/Qwen3.8-Flash-Next']:
    body = json.dumps({'model': c, 'messages': [{'role':'user','content':'hi'}], 'max_tokens': 10, 'tools': tools}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=50)
        d = json.loads(r.read())
        mc = d['choices'][0]['message']
        verdict = '调用了工具' if mc.get('tool_calls') else 'tools 接受(未触发)'
        print('%-44s tools: OK(%s)' % (c, verdict), flush=True)
    except urllib.error.HTTPError as e:
        print('%-44s tools: HTTP %d %s' % (c, e.code, e.read(140).decode(errors='ignore')[:100]), flush=True)

png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
img_msg = [{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+png}},{'type':'text','text':'这张图是什么颜色？一个词回答'}]}]
for c in ['Shanghai_AI_Laboratory/Intern-S2-Preview','ZhipuAI/GLM-5.2']:
    body = json.dumps({'model': c, 'messages': img_msg, 'max_tokens': 15}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=60)
        d = json.loads(r.read())
        print('%-44s vision: OK  回答=%s' % (c, d['choices'][0]['message']['content'][:40]), flush=True)
    except urllib.error.HTTPError as e:
        print('%-44s vision: HTTP %d %s' % (c, e.code, e.read(140).decode(errors='ignore')[:100]), flush=True)
