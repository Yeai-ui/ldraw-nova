import json, urllib.request

cfg = json.load(open('/config/models.json'))
tok = cfg['models'][0]['litellm_params']['api_key']
URL = 'https://api-inference.modelscope.cn/v1/chat/completions'
def call(model, payload_extra=None, timeout=60):
    body = json.dumps({'model': model, 'messages': [{'role':'user','content':'1+1=? 只回答数字'}], 'max_tokens': 10, **(payload_extra or {})}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(r.read())
        return 'OK  回答: %s' % str(d['choices'][0]['message']['content'])[:50]
    except urllib.error.HTTPError as e:
        return 'HTTP %d  %s' % (e.code, e.read(200).decode(errors='ignore')[:150])

for m in ['Qwen/Qwen3.5-27B', 'ZhipuAI/GLM-4.7-Flash', 'deepseek-ai/DeepSeek-V4-Flash-0731', 'MiniMax/MiniMax-M3', 'Qwen/Qwen3.5-397B-A17B']:
    print('%-38s %s' % (m, call(m)), flush=True)
