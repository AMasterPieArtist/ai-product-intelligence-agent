"""Explainable scenario recommendations from reviewed campaign evidence."""
import html
import json
from collections import Counter
from pathlib import Path

PRODUCTS = ('dify_app', 'coze_app')
NAMES = {'dify_app': 'Dify', 'coze_app': 'Coze'}
PERSONAS = {'all': '综合四类需求', 'quick_lookup': '快速查询', 'source_checker': '资料核查',
            'newcomer': '新员工操作', 'critical_reader': '谨慎审核'}
SCENARIOS = [
    ('facts', '基础信息与使用边界', ['EV001','EV002','EV003','EV004'], '负责人、适用人群、文件格式与跨文档信息查询'),
    ('expense', '报销政策与条件计算', ['EV005','EV006','EV007','EV008','EV009','EV010','EV011','EV012'], '新旧版本、城市额度、跨日计算和缺失凭证'),
    ('access', '账号开通与访问权限', ['EV013','EV014','EV020'], '申请步骤、RBAC、上传后查不到的排查'),
    ('upload', '文件准备与上传', ['EV015','EV016','EV022'], '扫描件、大小限制、脱敏与错误能力前提'),
    ('incident', '故障处置与响应', ['EV017','EV018','EV019'], 'P1/P2处置、提交字段、首次响应与修复边界'),
    ('governance', '信息边界与上线验收', ['EV021','EV023','EV024'], '资料缺失时拒答、验收条件与上线决策权'),
]


def outcome(cell, persona):
    if cell['execution'] != 'finished':
        return 'not_reviewed'
    task = cell['task_completion']
    if task != 'passed' or persona != 'source_checker':
        return task
    # A source-checking requirement cannot pass with missing or failed sources.
    return cell['source_authenticity']


def decide(rows, expected=None):
    expected = len(rows) if expected is None else expected
    stats = {p: Counter(outcome(r['products'][p], r['persona']) for r in rows) for p in PRODUCTS}
    for p in PRODUCTS:
        stats[p]['not_reviewed'] += max(0, expected - len(rows))
    pairs = Counter((outcome(r['products'][PRODUCTS[0]], r['persona']),
                     outcome(r['products'][PRODUCTS[1]], r['persona'])) for r in rows)
    shared = sorted({r['task_id'] for r in rows if all(outcome(r['products'][p], r['persona']) == 'failed' for p in PRODUCTS)})
    source_risks = {p: sum(r['products'][p]['source_authenticity'] == 'failed' for r in rows) for p in PRODUCTS}
    if not rows or len(rows) < expected or any(stats[p]['not_reviewed'] for p in PRODUCTS):
        code, title, why = 'pending', '评测未齐，暂不选型', '先完成本场景两套配置的运行与复核。'
    elif shared:
        code, title, why = 'shared_gap', '两套均需补齐关键子场景', '双方在' + '、'.join(shared) + '均有明确失败；其余子项可单独选择，不能按平均表现放行整个场景。'
    elif all(stats[p]['passed'] == len(rows) for p in PRODUCTS):
        code, title, why = 'both', '两套均满足本轮所选需求', '未观察到任务完成差异；下一步比较尚未测量的成本、接入和维护条件。'
    else:
        complete = [p for p in PRODUCTS if stats[p]['passed'] == len(rows)]
        a, b = pairs[('passed', 'failed')], pairs[('failed', 'passed')]
        if len(complete) == 1:
            preferred = complete[0]
            other = next(p for p in PRODUCTS if p != preferred)
            code, title = preferred, '优先' + NAMES[preferred] + '当前配置'
            why = ('所选需求全部通过；另一套存在明确失败。' if stats[other]['failed'] else
                   '所选需求的支持证据更完整；另一套仍有无法确定，不能称为已证实失败。')
        elif a and not b:
            code, title, why = 'dify_app', '有条件优先Dify', '明确配对差异偏向Dify，但仍有未满足或无法确定的子项，需要限定适用范围。'
        elif b and not a:
            code, title, why = 'coze_app', '有条件优先Coze', '明确配对差异偏向Coze，但仍有未满足或无法确定的子项，需要限定适用范围。'
        else:
            code, title, why = 'unclear', '暂不能给出单一优选', '存在交叉优劣或证据不足，请按具体任务拆分选择。'
    if code in PRODUCTS and source_risks[code]:
        title = '先复核' + NAMES[code] + '来源，再确认选型'
        why += ' 候选配置有明确来源错误，不应直接用于要求可追溯依据的业务。'
    return dict(code=code, title=title, why=why, stats={p:dict(stats[p]) for p in PRODUCTS},
                shared_gap_tasks=shared, source_risks=source_risks,
                paired=dict(both_pass=pairs[('passed','passed')], dify_only=pairs[('passed','failed')],
                            coze_only=pairs[('failed','passed')], both_fail=pairs[('failed','failed')]))


def build(data):
    result = dict(campaign=data['campaign'], method='scenario_decision_v1', views={})
    for persona in PERSONAS:
        cards = []
        for sid, title, tids, usage in SCENARIOS:
            rows = [r for r in data['rows'] if r['task_id'] in tids and (persona == 'all' or r['persona'] == persona)]
            n = len(tids) * (4 if persona == 'all' else 1)
            decision = decide(rows, n)
            subtasks = []
            for tid in tids:
                rs = [r for r in rows if r['task_id'] == tid]
                decision_one = decide(rs, 4 if persona == 'all' else 1)
                subtasks.append(dict(task_id=tid, question=rs[0]['question'] if rs else '待运行',
                                     decision=decision_one, evidence=rs))
            cards.append(dict(id=sid, name=title, usage=usage, expected=n, decision=decision, tasks=subtasks))
        result['views'][persona] = cards
    return result


def ratio(card, product):
    return f"{card['decision']['stats'][product].get('passed',0)}/{card['expected']}"


def write_decisions(folder, data):
    folder = Path(folder)
    result = build(data)
    lines = ['# 场景选型建议', '', '结论基于当前两套配置及AI辅助证据复核；优先建议用于试点选型，不代表生产上线批准。', '',
             '满足所选需求＝任务通过；资料核查还必须来源通过。未运行、未复核、无法确定均不会算作通过。', '',
             '| 业务场景 | 直接建议 | Dify满足需求/组合 | Coze满足需求/组合 | 判断依据 |', '|---|---|---:|---:|---|']
    for card in result['views']['all']:
        d = card['decision']
        lines.append(f"| {card['name']} | {d['title']} | {ratio(card,'dify_app')} | {ratio(card,'coze_app')} | {d['why']} |")
    lines += ['', '## 具体任务与适用限制', '']
    for card in result['views']['all']:
        lines += [f"### {card['name']}", '', card['usage'], '']
        for task in card['tasks']:
            lines.append(f"- {task['task_id']}：{task['decision']['title']}。{task['decision']['why']}")
    lines += ['', '## 推荐规则', '',
              '1. 数据缺失或未复核：暂不选型。',
              '2. 存在双方明确失败的子场景：先补齐，不用总体比例掩盖关键缺口。',
              '3. 两边所选需求全部通过：并列满足；成本与维护收益需另测。',
              '4. 一边全部通过：优先该配置；对方若仅证据不足，明确称证据更充分，不推断其错误。',
              '5. 都有缺口：仅在明确配对差异单向时给有条件建议；交叉差异不强行排序。',
              '6. 候选配置出现明确来源错误：先复核来源，再确认选型。', '',
              '规则是可解释的产品决策启发式，不是已验证的自动选型模型；不使用任意加权总分。',
              '6个场景分组是展示层对原24题的业务归类，未改变测试问题、Persona或原始标签。', '',
              'HTML版可切换用户需求并展开每条复核依据；详细原始记录在同目录campaign_matrix中定位。']
    (folder/'scenario_recommendations.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (folder/'scenario_recommendations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    options = ''.join(f'<option value="{p}">{html.escape(name)}</option>' for p,name in PERSONAS.items())
    scenario_options = ''.join(f'<option value="{s[0]}">{s[1]}</option>' for s in SCENARIOS)
    # JSON embedded in HTML must escape closing script tags from source answers/notes.
    payload = json.dumps(result,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>场景选型建议</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#182d44;font:15px/1.65 system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:30px 22px}h1{font-size:30px;margin:0}header{background:#19364a;color:white;padding:28px;border-radius:14px}header p{color:#dfebf1}.controls{position:sticky;top:0;background:#f4f6fa;padding:18px 0;z-index:1}select{font:inherit;padding:8px;border:1px solid #bac9d5;border-radius:6px;margin:5px 14px 5px 4px}#cards{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:white;border:1px solid #dce3ed;border-radius:12px;padding:22px}.card h2{margin:0;font-size:21px}.advice{font-size:22px;font-weight:700;color:#0d6662;margin:14px 0 8px}.warn .advice{color:#956010}.metric{display:flex;gap:20px;background:#f1f5f9;padding:12px;border-radius:7px}.metric b{font-size:24px}.hint{font-size:13px;color:#596d80}summary{cursor:pointer;color:#205581;margin:12px 0}details{border-top:1px solid #e0e6ed}details p{overflow-wrap:anywhere}.evidence{font-size:13px;background:#f6f8fa;padding:12px;border-radius:6px}footer{margin-top:24px;font-size:13px;color:#526579}button{font:inherit;padding:7px 12px} @media(max-width:760px){#cards{grid-template-columns:1fr}main{padding:16px}.controls{position:static}}</style>
<main><header><h1>哪个业务场景，优先哪套配置？</h1><p>先看选择建议，再看限制与证据。24题 · 4种用户需求 · 2套应用</p><p>当前测试配置的试点建议；基于AI辅助证据复核，不是上线批准或平台通用排名。</p></header>
<div class="controls"><label>业务场景<select id="scenario"><option value="all">全部六类</option>__SCENARIOS__</select></label><label>谁来使用<select id="persona">__OPTIONS__</select></label></div><div id="cards"></div>
<footer><p>数字为满足所选需求的组合数/预定组合数。资料核查同时要求任务与来源通过；无法确定不当作错误，也不当作通过。不同Persona不是独立真实用户。成本、维护投入及相对人工收益未测量。</p><details><summary>为什么会给出这些建议？</summary><p>先检查数据完整，再检查双方共同失败；双方全部通过时并列；一方全部通过时优先该配置；其他情况只对单向明确配对差异给有条件建议。候选有来源错误则先复核。整个场景有共同失败时，不用平均比例掩盖该缺口。分组和规则均是可调整的展示层决策规则。</p></details></footer></main>
<script id="data" type="application/json">__PAYLOAD__</script><script>
const data=JSON.parse(document.getElementById('data').textContent);
const names={dify_app:'Dify',coze_app:'Coze'}, labels={passed:'通过',failed:'失败',inconclusive:'无法确定',not_reviewed:'未复核'};
function esc(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function metric(c,p){const s=c.decision.stats[p];return '<div>'+names[p]+' <b>'+(s.passed||0)+'/'+c.expected+'</b><div class="hint">失败 '+(s.failed||0)+' · 无法确定 '+(s.inconclusive||0)+' · 未复核 '+(s.not_reviewed||0)+'</div></div>';}
function evidence(t){return t.evidence.map(r=>'<div class="evidence"><b>'+esc(r.task_id+' / '+r.persona)+'</b>'+Object.entries(r.products).map(([p,c])=>'<p><b>'+names[p]+'</b>：任务'+esc(labels[c.task_completion])+' / 来源'+esc(labels[c.source_authenticity])+'</p><p>'+esc(c.evidence_note)+'</p><p>'+esc(c.user_fit_note)+'</p>').join('')+'</div>').join('');}
function render(){const persona=document.getElementById('persona').value,sid=document.getElementById('scenario').value;document.getElementById('cards').innerHTML=data.views[persona].filter(c=>sid==='all'||c.id===sid).map(c=>'<section class="card '+(['shared_gap','pending','unclear'].includes(c.decision.code)?'warn':'')+'"><h2>'+esc(c.name)+'</h2><div class="hint">'+esc(c.usage)+'</div><p class="advice">'+esc(c.decision.title)+'</p><p>'+esc(c.decision.why)+'</p><div class="metric">'+metric(c,'dify_app')+metric(c,'coze_app')+'</div><details><summary>展开具体任务：哪些能用，哪些要先补？</summary>'+c.tasks.map(t=>'<details><summary>'+esc(t.task_id+' · '+t.decision.title)+'</summary><p>'+esc(t.question)+'</p><p>'+esc(t.decision.why)+'</p>'+evidence(t)+'</details>').join('')+'</details></section>').join('');}
document.getElementById('persona').addEventListener('change',render);document.getElementById('scenario').addEventListener('change',render);render();
</script></html>'''
    page = page.replace('__OPTIONS__',options).replace('__SCENARIOS__',scenario_options).replace('__PAYLOAD__',payload)
    (folder/'scenario_recommendations.html').write_text(page,encoding='utf-8')
    return result
