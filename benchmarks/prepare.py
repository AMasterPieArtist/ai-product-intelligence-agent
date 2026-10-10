"""Offline plan builder. Creates a bounded run config; never opens a browser."""
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
PERSONAS=['quick_lookup','source_checker','newcomer','critical_reader']

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare(project_root,campaign='expanded_v1',batch='smoke',mode='rules',settings_path=None):
    root=Path(project_root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',campaign):raise ValueError('campaign仅使用英文字母、数字、下划线')
    if mode not in ('rules','model'):raise ValueError('mode应为rules或model')
    runner=root/'evaluator/runner.py'
    if not runner.is_file():raise FileNotFoundError('请将Notebook和benchmarks放到完整项目根目录')
    settings_file=Path(settings_path) if settings_path else HERE/'app_settings.json'
    if not settings_file.is_file():raise FileNotFoundError('请复制benchmarks/app_settings.example.json为app_settings.json，并填写自己的应用配置')
    settings=read(settings_file)
    products=settings['products']
    for pid in ('dify_app','coze_app'):
        p=products[pid]
        if p.get('material_confirmed') is not True:raise ValueError('请先给两套应用配置本轮8份资料，再将material_confirmed设为true：'+pid)
        if 'REPLACE_WITH_' in p.get('url','') or not p.get('url','').startswith(('https://','http://')):raise ValueError('请填写应用URL')
        if any('请记录' in str(v) for v in p.get('settings',{}).values()):raise ValueError('请填写应用设置；无法确认的项明确写unknown：'+pid)
    suite=read(HERE/'tasks.json');batches=read(HERE/'batches.json')
    comparison_choices=None
    if batch in ('human_first','agent_first'):
        comparison_choices=read(HERE/'human_comparison.json')['records']
        comparison_choices=[r for r in comparison_choices if r['order']==batch]
        ids=list(dict.fromkeys(r['task_id'] for r in comparison_choices))
    elif batch=='smoke':ids=['EV001']
    elif batch in batches:ids=batches[batch]
    else:raise ValueError('batch只能为smoke、1至6，或人工对照分组human_first/agent_first')
    all_jobs=[dict(product=p,task=t['id'],persona=persona) for t in suite['tasks'] for persona in t['personas'] for p in products]
    jobs=[job for job in all_jobs if job['task'] in ids]
    if comparison_choices is not None:
        keys={(r['product'],r['task_id'],r['persona']) for r in comparison_choices}
        jobs=[j for j in jobs if (j['product'],j['task'],j['persona']) in keys]
    material=[dict(document_id=d['id'],path=str((HERE/d['path']).resolve()),sha256=digest(HERE/d['path']),remote_names=d['remote_names']) for d in suite['documents']]
    code_files=['stability.py','runner.py','adapters.py','engine.py','core.py','browser_runtime.py','review.py','data/personas.json']
    fingerprint=dict(suite_sha256=digest(HERE/'tasks.json'),gold_sha256=digest(HERE/'gold_review.json'),
        material_hashes={x['document_id']:x['sha256'] for x in material},
        code_hashes={n:digest(root/'evaluator'/n) for n in code_files},products=products,operation_mode=mode,
        study='human_comparison' if comparison_choices is not None else 'expanded',
        comparison_assignment=[[r['pair_id'],r['order']] for r in read(HERE/'human_comparison.json')['records']] if comparison_choices is not None else None)
    campaign_dir=root/'evaluation/expanded_campaigns'/campaign
    manifest=campaign_dir/'campaign_manifest.json'
    if manifest.exists() and read(manifest)!=fingerprint:raise ValueError('代码、材料或应用配置已变化，请换一个campaign名称；不能混入同一轮')
    completed=set()
    for path in sorted((campaign_dir/'results').glob('*/*/record.json')):
        r=read(path)
        if r.get('agent_status')=='finished':completed.add((r['product_id'],r['task']['id'],r['persona_id']))
    if batch!='smoke' and comparison_choices is None:
        expected={(j['product'],j['task'],j['persona']) for j in all_jobs if j['task']=='EV001'}
        if not expected.issubset(completed):raise ValueError('先运行smoke的8个组合，并检查来源采集和回答，再开始批次1至6')
    jobs=[j for j in jobs if (j['product'],j['task'],j['persona']) not in completed]
    if not jobs:return dict(planned_runs=0,note='本批组合已全部执行完成，不重复启动。')
    if not manifest.exists():write(manifest,fingerprint)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    cfg=dict(project_root=str(root),suite_path=str(HERE/'tasks.json'),material_manifest=material,
        output_dir=str(campaign_dir/'results'/stamp),products=products,
        selected_products=list(products),selected_tasks=ids,selected_runs=jobs,max_runs=len(jobs),
        max_calls_per_run=26,operation_mode=mode,snapshot_policy='transitions' if mode=='rules' else 'all',
        max_operation_steps=80 if mode=='rules' else 12,headless=False,stop_on_error=False,
        campaign_id=campaign,batch_id=batch,persona_version='page_sources_v3',protocol='expanded_business_24_v1')
    path=campaign_dir/'requests'/(stamp+'.json');write(path,cfg)
    return dict(config_path=str(path),output_dir=cfg['output_dir'],planned_runs=len(jobs),
        personas=dict(Counter(j['persona'] for j in jobs)),operation_mode=mode,
        max_decision_calls=sum(0 if j['persona']=='quick_lookup' else 1 for j in jobs) if mode=='rules' else 26*len(jobs),
        note='已完成组合自动跳过；运行失败或尚未执行组合将保留。计划上限不是实际花费。')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project-root',required=True);p.add_argument('--campaign',default='expanded_v1');p.add_argument('--batch',default='smoke');p.add_argument('--mode',choices=['rules','model'],default='rules');a=p.parse_args()
    print(json.dumps(prepare(a.project_root,a.campaign,a.batch,a.mode),ensure_ascii=False,indent=2))
