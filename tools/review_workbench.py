"""Offline review dashboard. Hints never change review decisions or call a model."""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def resolve_material(entry, project_root):
    candidates = [Path(entry.get('path', ''))]
    name = entry['document_id']
    candidates += [project_root/'benchmarks/materials'/name, project_root/'evaluator/data/materials'/name,
                   project_root/'evaluator/dataset/materials'/name,
                   project_root/'data/test_documents'/name, project_root/name]
    mismatches = []
    for path in candidates:
        if not path.is_file(): continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.get('sha256'):
            mismatches.append(str(path)); continue
        if path.suffix.lower() not in {'.txt', '.md'}:
            return dict(document_id=name, status='manual_file_review', path=str(path), text='', note='哈希一致；PDF/DOCX正文请人工查看')
        return dict(document_id=name, status='hash_matched', path=str(path), text=path.read_text(encoding='utf-8-sig'), note='本地文件哈希与该运行记录一致')
    return dict(document_id=name, status='hash_mismatch' if mismatches else 'missing', text='', note='本地文件不符合该轮哈希' if mismatches else '未找到该轮本地材料')

def inspect_record(record, review, project_root):
    materials = [resolve_material(e, project_root) for e in record.get('material_manifest', [])]
    finished = [t for t in record.get('turns', []) if t.get('status') == 'finished']
    answers = [t.get('answer_clean') or t.get('answer_raw') or '' for t in finished]
    latest = answers[-1] if answers else ''
    quotes = list(dict.fromkeys(re.findall(r'[“「]([^”」\n]{4,})[”」]', latest)))
    quote_checks = []
    for quote in quotes:
        matches = [m['document_id'] for m in materials if m['text'] and quote in m['text']]
        quote_checks.append(dict(text=quote, exact_match_documents=matches,
                                 status='exact_substring' if matches else 'no_exact_match'))
    refs = record.get('task', {}).get('reference_answers', [])
    names = [m['document_id'] for m in materials if m['document_id'] in latest]
    hints = []
    if record.get('agent_status') != 'finished':
        priority = 0; hints.append('执行异常：先检查页面/适配器；执行失败不能当作产品回答错误')
    elif record.get('evaluation', {}).get('initial_answer_rule') == 'failed':
        priority = 1; hints.append('首答未满足词面规则；需要看原文判断，规则失败不是最终语义判定')
    else:
        priority = 2
    if any(c['status'] == 'no_exact_match' for c in quote_checks):
        priority = min(priority, 1); hints.append('引号片段未精确匹配本地正文：可能改写、排版差异或来源问题，需核对')
    if record.get('task', {}).get('requires_human_review'):
        hints.append('此任务要求语义复核；计算、版本、操作步骤不能靠关键词直接通过')
    if not names:
        hints.append('答案正文未发现本轮已知文件名；还需看页面来源卡片/截图')
    if any(m['status'] in ('missing', 'hash_mismatch') for m in materials):
        hints.append('材料缺失或哈希不同，来源真实性保留不确定')
    if review.get('task_completion') in ('passed', 'failed') and review.get('source_authenticity') in ('passed', 'failed'):
        priority = 3; hints.append('已有人工作出任务与来源判断；保留原判断，可按需要抽检')
    if not hints: hints.append('普通待复核；词面匹配不能证明语义、引用归属或实际检索')
    return dict(run_id=record['run_id'], priority=priority, hints=hints, record=record,
                review=review, materials=materials, quote_checks=quote_checks,
                reference_answers=refs,
                reference_substrings_in_first_answer=[a for a in refs if answers and a in answers[0]])

def build(folder, project_root=ROOT):
    folder = Path(folder).resolve(); project_root = Path(project_root).resolve()
    paths = sorted(folder.glob('*/record.json'))
    if not paths: raise ValueError('目录中没有业务/公开数据运行记录（需要 */record.json）')
    records = [load_json(p) for p in paths]
    if any(not r.get('task') for r in records): raise ValueError('本工具需要包含task的多轮记录格式；早期页面探测记录请查看原报告')
    review_path = folder/'human_reviews.json'
    reviews = load_json(review_path) if review_path.is_file() else {}
    # Preserve every existing field and untouched run; no automatic pass/fail writeback.
    for record in records:
        reviews.setdefault(record['run_id'], dict(task_completion='not_reviewed', source_authenticity='not_reviewed', reviewer='', evidence_note='', user_fit_note=''))
    items = sorted([inspect_record(r, reviews[r['run_id']], project_root) for r in records], key=lambda x: (x['priority'], x['run_id']))
    (folder/'review_queue.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    esc = html.escape
    panels = []
    statuses = ['not_reviewed', 'passed', 'failed', 'inconclusive']
    for i, item in enumerate(items):
        record = item['record']; rv = item['review']; rid = item['run_id']
        fields = []
        for field, label in [('task_completion','任务完成'),('source_authenticity','来源真实性')]:
            opts = ''.join(f'<option value="{v}"'+(' selected' if rv.get(field, 'not_reviewed') == v else '')+f'>{v}</option>' for v in statuses)
            fields.append(f'<label>{label}<select data-run="{i}" data-field="{field}">{opts}</select></label>')
        for field,label in [('reviewer','复核人'),('evidence_note','证据定位：文档、片段、轮次'),('user_fit_note','用户适配：满足的需求/仍有缺口')]:
            fields.append(f'<label>{label}<textarea data-run="{i}" data-field="{field}">{esc(str(rv.get(field,"")))}</textarea></label>')
        turns = ''.join(f'<h4>第{t.get("turn",n+1)}轮：{esc(str(t.get("question","")))}</h4><pre>{esc(str(t.get("answer_clean") or t.get("answer_raw") or "未获得完整回答"))}</pre>' for n,t in enumerate(record.get('turns',[])))
        material_html = ''.join(f'<details><summary>{esc(m["document_id"])} · {esc(m["status"])}</summary><p>{esc(m["note"])}</p><pre>{esc(m["text"])}</pre></details>' for m in item['materials'])
        artifacts = []
        run_dir = folder/rid
        for p in sorted(run_dir.glob('*.png')):
            artifacts.append(f'<a href="{esc(rid+"/"+p.name,quote=True)}" target="_blank">{esc(p.name)}</a>')
        hints = ''.join(f'<li>{esc(h)}</li>' for h in item['hints'])
        panels.append(f'<section><h2>P{item["priority"]} · {esc(rid)}</h2><p>执行：{esc(str(record.get("agent_status")))} ｜ 首答规则：{esc(str(record.get("evaluation",{}).get("initial_answer_rule")))}</p><ul>{hints}</ul>{turns}<details><summary>本地判定依据与匹配提示</summary><pre>{esc(json.dumps(dict(reference_answers=item["reference_answers"], oracle=record["task"].get("oracle"), reference_substrings_in_first_answer=item["reference_substrings_in_first_answer"], quote_checks=item["quote_checks"]),ensure_ascii=False,indent=2))}</pre>{material_html}</details><p>截图：{" · ".join(artifacts) or "未找到本地截图"}</p><div class="form">{"".join(fields)}</div></section>')
    payload = json.dumps(dict(reviews=reviews, order=[i['run_id'] for i in items]), ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    template = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>离线复核工作台</title><style>body{font:16px/1.6 system-ui;max-width:1080px;margin:24px auto;padding:0 16px;background:#f5f7fa;color:#202b3b}section{background:white;padding:22px;margin:20px 0;border:1px solid #dde3eb;border-radius:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f3f7;padding:14px}textarea,select{display:block;width:100%;box-sizing:border-box;padding:8px;font:inherit}textarea{min-height:72px}label{display:block;margin:12px 0}button{padding:10px 20px;font:inherit}header{position:sticky;top:0;background:#f5f7fa;padding:12px;border-bottom:1px solid #ccd4df}a{color:#215db0}</style><header><strong>离线复核工作台</strong><br>提示仅辅助定位，不自动填写通过/失败。导出后将文件放回本实验目录，替换 human_reviews.json，再重建矩阵。<br><button id="export">导出 human_reviews.json</button><span id="message"></span></header><p>P0执行异常 → P1优先核查 → P2待复核 → P3已有明确人工判断。正文无文件名不等于页面无来源。计时为表单编辑经过时间估计，不是效率提升证明。</p>__PANELS__<script id="payload" type="application/json">__PAYLOAD__</script><script>
const data=JSON.parse(document.getElementById('payload').textContent), edits=new Map();
document.querySelectorAll('[data-field]').forEach(el=>{
 el.addEventListener('input',()=>{
  const rid=data.order[Number(el.dataset.run)];
  if(!edits.has(rid))edits.set(rid,performance.now());
  data.reviews[rid][el.dataset.field]=el.value;
 });
});
document.getElementById('export').addEventListener('click',()=>{
 for(const [rid,start] of edits){
  const r=data.reviews[rid];
  if(([r.task_completion,r.source_authenticity].some(v=>['passed','failed'].includes(v)))&&(!String(r.reviewer||'').trim()||!String(r.evidence_note||'').trim())){
   document.getElementById('message').textContent=' 请补充复核人和证据定位：'+rid;return;
  }
 }
 const result=structuredClone(data.reviews);
 for(const [rid,start] of edits){
  result[rid].review_seconds=Number((Number(result[rid].review_seconds||0)+(performance.now()-start)/1000).toFixed(1));
  result[rid].review_seconds_measurement='form_edit_elapsed_estimate';
 }
 const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='human_reviews.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.getElementById('message').textContent=' 已导出；检查下载文件名，放回本实验目录后重建矩阵。';
});
</script></html>'''
    target = folder/'review_workbench.html'
    target.write_text(template.replace('__PANELS__',''.join(panels)).replace('__PAYLOAD__',payload), encoding='utf-8')
    return dict(runs=len(items), dashboard=str(target), queue=str(folder/'review_queue.json'), human_reviews_changed=False)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--project-root',default=str(ROOT));args=parser.parse_args()
    print(json.dumps(build(args.folder,args.project_root),ensure_ascii=False,indent=2))
