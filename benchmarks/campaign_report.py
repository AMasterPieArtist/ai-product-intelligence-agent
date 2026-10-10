"""Offline matrix from records + reviews, never cached batch matrices."""
import html
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
PRODUCTS = ('dify_app', 'coze_app')
PERSONAS = {'quick_lookup': '快速查询', 'source_checker': '资料核查',
            'newcomer': '新员工', 'critical_reader': '谨慎审核'}
LABELS = {'passed': '通过', 'failed': '失败', 'inconclusive': '无法确定', 'not_reviewed': '未复核'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def collect(folder, suite=None):
    folder = Path(folder)
    manifest = read(folder / 'campaign_manifest.json') if (folder / 'campaign_manifest.json').exists() else None
    if suite is None and manifest and hashlib.sha256((HERE / 'tasks.json').read_bytes()).hexdigest() != manifest['suite_sha256']:
        raise ValueError('任务集与campaign指纹不一致，请恢复对应版本')
    suite = suite or read(HERE / 'tasks.json')
    tasks = {t['id']: t for t in suite['tasks']}
    allowed = {(p, t, u) for p in PRODUCTS for t in tasks for u in PERSONAS}
    finished, latest, attempts = {}, {}, []
    for run in sorted((folder / 'results').glob('*')):
        reviews = read(run / 'human_reviews.json') if (run / 'human_reviews.json').exists() else {}
        paths = sorted(run.glob('*/record.json'))
        if paths and manifest:
            config = read(run / 'config.json')
            if config.get('campaign_id') != folder.name or config.get('products') != manifest['products']:
                raise ValueError('批次配置与campaign不一致：' + run.name)
        records = [read(path) for path in paths]
        unknown = set(reviews) - {r['run_id'] for r in records}
        if unknown:
            raise ValueError('复核引用不存在的run_id：' + ', '.join(sorted(unknown)))
        for path, record in zip(paths, records):
            if manifest and {m['document_id']: m['sha256'] for m in record.get('material_manifest', [])} != manifest['material_hashes']:
                raise ValueError('材料指纹与campaign不一致：' + str(path))
            key = (record['product_id'], record['task']['id'], record['persona_id'])
            if key not in allowed:
                raise ValueError('非本任务集组合：' + str(key))
            review = reviews.get(record['run_id'], {})
            for field in ('task_completion', 'source_authenticity'):
                status = review.get(field, 'not_reviewed')
                if status not in LABELS:
                    raise ValueError('无效复核状态：' + str(status))
                if status in ('passed', 'failed') and not all(review.get(k, '').strip() for k in ('reviewer', 'evidence_note')):
                    raise ValueError('通过/失败须附复核人与证据：' + record['run_id'])
            entry = dict(record=record, review=review,
                         record_path=path.relative_to(folder).as_posix(),
                         report_path=(path.parent / 'report.md').relative_to(folder).as_posix())
            attempts.append(entry)
            latest[key] = entry
            if record['agent_status'] == 'finished':
                if key in finished:
                    raise ValueError('同一campaign发现重复完成组合：' + str(key))
                finished[key] = entry
    rows = []
    for tid, task in tasks.items():
        for persona in PERSONAS:
            cells = {}
            for product in PRODUCTS:
                key = (product, tid, persona)
                entry = finished.get(key, latest.get(key))
                cell = dict(execution='not_run', task_completion='not_reviewed', source_authenticity='not_reviewed',
                            turns=0, reviewer='', evidence_note='', user_fit_note='', record_path='', report_path='')
                if entry:
                    record, review = entry['record'], entry['review']
                    cell.update(execution=record['agent_status'], turns=len(record.get('turns', [])),
                                record_path=entry['record_path'], report_path=entry['report_path'])
                    if key in finished:
                        for field in ('task_completion', 'source_authenticity'):
                            cell[field] = review.get(field, 'not_reviewed')
                        for field in ('reviewer', 'evidence_note', 'user_fit_note'):
                            cell[field] = review.get(field, '')
                cells[product] = cell
            rows.append(dict(task_id=tid, scenario=task.get('scenario', ''), question=task.get('question', ''),
                             persona=persona, products=cells))
    return dict(campaign=folder.name, suite_id=suite['suite_id'], rows=rows,
                planned=len(allowed), completed=len(finished), attempts=len(attempts),
                errors=sum(e['record']['agent_status'] != 'finished' for e in attempts),
                reviewers=dict(Counter(e['review'].get('reviewer', '未填写') for e in finished.values())))


def counts(data, product, field, persona=None):
    return Counter(row['products'][product][field] for row in data['rows']
                   if (persona is None or row['persona'] == persona) and row['products'][product]['execution'] == 'finished')


def summary_text(data):
    task_count = len(data['rows']) // len(PERSONAS)
    lines = ['# 扩展轮进度与复核摘要', '',
             f"计划：{task_count}题 × 4种Persona × 2套应用 = {data['planned']}个组合。已完成{data['completed']}/{data['planned']}；记录到{data['attempts']}次尝试，其中异常{data['errors']}次。", '',
             '结论来自填写的复核结果；AI辅助复核不是独立人工盲评，Persona不是独立真实用户。', '',
             '[先看场景选型建议](scenario_recommendations.html) · [完整矩阵](campaign_matrix.html) · [结果分析](campaign_analysis.md)', '',
             '| 应用 | Persona | 完成 | 任务通过 | 任务失败 | 无法确定 | 未复核 |', '|---|---|---:|---:|---:|---:|---:|']
    for product in PRODUCTS:
        for persona in PERSONAS:
            c = counts(data, product, 'task_completion', persona)
            lines.append(f"| {product} | {persona} | {sum(c.values())}/{task_count} | " + ' | '.join(str(c[s]) for s in LABELS) + ' |')
    lines += ['', '## 来源复核分布', '', '| 应用 | Persona | 通过 | 失败 | 无法确定 | 未复核 |', '|---|---|---:|---:|---:|---:|']
    for product in PRODUCTS:
        for persona in PERSONAS:
            c = counts(data, product, 'source_authenticity', persona)
            lines.append(f'| {product} | {persona} | ' + ' | '.join(str(c[s]) for s in LABELS) + ' |')
    return '\n'.join(lines) + '\n'


def cell_text(cell):
    return f"{cell['execution']} / {LABELS[cell['task_completion']]} / {LABELS[cell['source_authenticity']]} / {cell['turns']}轮"


def analysis_text(data):
    lines = ['# 竞品配置比较：复核结果与决策线索', '',
             '只比较本campaign中两套应用的已测配置；Persona会话不是独立真实用户或重复稳定性试验。', '',
             '| 应用 | 已完成 | 任务通过/失败/无法确定/未复核 | 通过占全部完成组合 | 来源通过/失败/无法确定/未复核 |', '|---|---:|---|---:|---|']
    for p in PRODUCTS:
        t, s = counts(data, p, 'task_completion'), counts(data, p, 'source_authenticity')
        rate = f"{t['passed']/sum(t.values()):.1%}" if sum(t.values()) else '无样本'
        lines.append(f"| {p} | {sum(t.values())} | {' / '.join(str(t[x]) for x in LABELS)} | {rate} | {' / '.join(str(s[x]) for x in LABELS)} |")
    lines += ['', '## 相同任务与Persona的配对结果', '',
              '仅在两边均完成且任务复核明确为通过/失败时比较；其他状态排除并计数。', '',
              '| 两边通过 | 仅Dify通过 | 仅Coze通过 | 两边失败 | 排除 |', '|---:|---:|---:|---:|---:|']
    pairs = Counter()
    for row in data['rows']:
        a, b = (row['products'][p] for p in PRODUCTS)
        if not all(c['execution'] == 'finished' and c['task_completion'] in ('passed', 'failed') for c in (a, b)):
            pairs['excluded'] += 1
        else:
            pairs[(a['task_completion'], b['task_completion'])] += 1
    lines += ['| ' + ' | '.join(str(pairs[k]) for k in [('passed', 'passed'), ('passed', 'failed'), ('failed', 'passed'), ('failed', 'failed'), 'excluded']) + ' |', '',
              '## 如何使用结果', '',
              '- 快速查询看首答核心与必要条件；核查场景同时看任务和来源；新员工看解释与下一步；谨慎审核看版本和边界。',
              '- 失败记录支持提出修复候选；优先回看关键条件与明确来源错配。无法确定先补采集或复核，不能一律归因于产品。',
              '- 模型、检索与来源展示配置不同，不能由本报告分离平台、模型和检索的因果贡献。',
              '- 同题多Persona失败不等于多个独立缺陷；数量均为组合记录。',
              '- 未测得人工效率提升或相对人工的准确性增益。运行时间与轮数不能代替人工主动时间。', '', '## 明确来源失败记录', '']
    for row in data['rows']:
        for p, cell in row['products'].items():
            if cell['source_authenticity'] == 'failed':
                lines.append(f"- [{p} / {row['task_id']} / {row['persona']}]({quote(cell['report_path'], safe='/')})：{safe(cell['evidence_note'])}")
    lines += ['', '## 复核署名分布', '', json.dumps(data['reviewers'], ensure_ascii=False), '',
              '原记录和复核JSON为权威输入；单批matrix.md可能未重建，本报告不读取其缓存。']
    return '\n'.join(lines) + '\n'


def write_reports(folder, data):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'campaign_summary.md').write_text(summary_text(data), encoding='utf-8')
    (folder / 'campaign_analysis.md').write_text(analysis_text(data), encoding='utf-8')
    lines = ['# 业务任务 × Persona × 应用：全量适配矩阵', '',
             f"Campaign：{safe(data['campaign'])}；{len(data['rows'])}行，{data['planned']}个预定组合。", '',
             '每格：执行 / 任务复核 / 来源复核 / 轮数。不将finished视为业务通过。', '',
             '| 任务 | 用户需求 | Dify | Coze |', '|---|---|---|---|']
    table = []
    for row in data['rows']:
        cells, htmlcells = [], []
        for p in PRODUCTS:
            c = row['products'][p]
            link = quote(c['report_path'], safe='/')
            cells.append(f'[{cell_text(c)}]({link})' if link else cell_text(c))
            details = ''.join(f'<p><b>{label}</b> {html.escape(c[field])}</p>' for label, field in
                              [('复核人', 'reviewer'), ('证据依据', 'evidence_note'), ('用户适配', 'user_fit_note')])
            htmlcells.append(f'<td><b>{html.escape(cell_text(c))}</b><details><summary>查看复核依据</summary>{details}' +
                             (f'<a href="{html.escape(link)}">原始对话报告</a>' if link else '') + '</details></td>')
        lines.append('| ' + ' | '.join(map(safe, [row['task_id'] + ' ' + row['scenario'], PERSONAS[row['persona']], *cells])) + ' |')
        flags = ' '.join(c['task_completion'] + ' ' + c['source_authenticity'] for c in row['products'].values())
        table.append(f'<tr data-persona="{row["persona"]}" data-status="{flags}"><td><b>{row["task_id"]}</b> {html.escape(row["scenario"])}<p>{html.escape(row["question"])}</p></td><td>{PERSONAS[row["persona"]]}</td>' + ''.join(htmlcells) + '</tr>')
    (folder / 'campaign_matrix.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (folder / 'campaign_matrix.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    options = ''.join(f'<option value="{p}">{name}</option>' for p, name in PERSONAS.items())
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>业务适配矩阵</title>
<style>body{font:15px/1.65 system-ui,sans-serif;margin:24px;color:#172b43;background:#f5f7fa}main{max-width:1500px;margin:auto}h1{font-size:27px}header{background:white;padding:22px;border-radius:12px}input,select{padding:9px;border:1px solid #aebdcc;border-radius:5px;margin:5px}table{border-collapse:collapse;width:100%;background:white;margin-top:18px}th,td{border:1px solid #d5dee8;padding:13px;text-align:left;vertical-align:top}th{background:#eaf0f6}td:first-child{width:24%}td:nth-child(2){width:9%}details p{overflow-wrap:anywhere}summary{cursor:pointer;color:#235c9b}a{color:#235c9b}.scroll{overflow:auto}p{margin:7px 0}</style>
<main><header><h1>业务任务 × Persona × 应用适配矩阵</h1><p>__OVERVIEW__</p><p>每格：执行 / 任务复核 / 来源复核 / 轮数。AI辅助证据复核不等于独立人工盲评；来源无法确定不等于错误。</p>
<label>搜索任务 <input id="query" placeholder="题号、关键词"></label><label>用户需求 <select id="persona"><option value="">全部</option>__OPTIONS__</select></label><label>含任一状态 <select id="status"><option value="">全部</option><option value="failed">失败</option><option value="inconclusive">无法确定</option><option value="not_reviewed">未复核</option></select></label><span id="count"></span></header>
<div class="scroll"><table><thead><tr><th>业务任务</th><th>用户需求</th><th>Dify</th><th>Coze</th></tr></thead><tbody>__ROWS__</tbody></table></div><p>复核说明已嵌入，可离线展开；原始对话链接需与原项目results目录一起保存。</p></main>
<script>const rows=[...document.querySelectorAll('tbody tr')];function filter(){const q=document.querySelector('#query').value.toLowerCase(),p=document.querySelector('#persona').value,s=document.querySelector('#status').value;let n=0;for(const r of rows){const show=(!q||r.textContent.toLowerCase().includes(q))&&(!p||r.dataset.persona===p)&&(!s||r.dataset.status.split(' ').includes(s));r.hidden=!show;if(show)n++;}document.querySelector('#count').textContent=n+' / '+rows.length+'行';}for(const id of ['query','persona','status'])document.getElementById(id).addEventListener('input',filter);filter();</script></html>'''
    overview = f"{data['campaign']} · 已完成 {data['completed']}/{data['planned']} · {data['attempts']}次尝试 · {data['errors']}次异常"
    page = page.replace('__OVERVIEW__', html.escape(overview)).replace('__OPTIONS__', options).replace('__ROWS__', ''.join(table))
    (folder / 'campaign_matrix.html').write_text(page, encoding='utf-8')
    try:
        from .decision_report import write_decisions
    except ImportError:
        from decision_report import write_decisions
    write_decisions(folder, data)
    return folder / 'campaign_summary.md'
