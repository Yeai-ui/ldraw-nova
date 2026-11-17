import json, urllib.request

cfg = json.load(open('/config/models.json'))
tok = cfg['models'][0]['litellm_params']['api_key']
URL = 'https://api-inference.modelscope.cn/v1/chat/completions'
tools = [{'type':'function','function':{'name':'place_brick','description':'place a brick at coords','parameters':{'type':'object','properties':{'x':{'type':'integer'},'colour':{'type':'string'}},'required':['x','colour']}}}]
body = json.dumps({'model': 'Shanghai_AI_Laboratory/Intern-S2-Preview',
    'messages': [{'role':'user','content':'请在 x=3 处放置一块红色积木，调用工具完成'}],
    'max_tokens': 200, 'tools': tools, 'tool_choice': 'auto'}).encode()
req = urllib.request.Request(URL, data=body, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
r = urllib.request.urlopen(req, timeout=60)
d = json.loads(r.read())
mc = d['choices'][0]['message']
if mc.get('tool_calls'):
    tc = mc['tool_calls'][0]
    print('真实触发 tool_calls ✅')
    print('  name:', tc['function']['name'])
    print('  args:', tc['function']['arguments'][:100])
else:
    print('未触发 tool_calls，回复:', str(mc.get('content'))[:150])
