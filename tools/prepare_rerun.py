"""Prepare an exact-combination rerun config, offline. Does not start a run."""
import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path, PureWindowsPath
ROOT=Path(__file__).resolve().parents[1]

def remap_path(value, root):
    old=Path(value)
    if old.is_file(): return old.resolve()
    parts=PureWindowsPath(value).parts
    aliases = {'benchmarks': 'benchmarks', 'evaluator': 'evaluator',
               'expanded_validation': 'benchmarks', 'day7_dataset': 'evaluator',
               'day6_business': 'evaluator', 'evaluation': 'evaluation', 'data': 'data'}
    for anchor, current in aliases.items():
        if anchor in parts:
            candidate=root.joinpath(current, *parts[parts.index(anchor)+1:])
            if candidate.is_file():return candidate.resolve()
    candidate=root/PureWindowsPath(value).name
    if candidate.is_file():return candidate.resolve()
    raise FileNotFoundError('找不到配置中的本地文件：'+value)

def prepare(folder, scope='execution_errors', project_root=ROOT, operation_mode=None):
    folder=Path(folder).resolve();root=Path(project_root).resolve()
    if not (folder/'config.json').is_file():raise ValueError('此结果目录缺少config.json；请选包含原配置的包含config.json的完整实验目录')
    config=json.loads((folder/'config.json').read_text(encoding='utf-8'));reviews={}
    if (folder/'human_reviews.json').is_file():reviews=json.loads((folder/'human_reviews.json').read_text(encoding='utf-8'))
    records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*/record.json'))]
    if scope not in ('execution_errors','review_failed','unreviewed'):raise ValueError('未知重测范围')
    choices=[]
    for r in records:
        review=reviews.get(r['run_id'],{})
        selected=(r['agent_status']!='finished') if scope=='execution_errors' else (r['agent_status']=='finished' and any(review.get(k)=='failed' for k in ('task_completion','source_authenticity'))) if scope=='review_failed' else (r['agent_status']=='finished' and any(review.get(k,'not_reviewed')=='not_reviewed' for k in ('task_completion','source_authenticity')))
        if selected:choices.append(dict(product=r['product_id'],task=r['task']['id'],persona=r['persona_id']))
    if not choices:return dict(planned_runs=0,config_written=False,note='此范围没有需要重测的组合；不创建空实验')
    new=copy.deepcopy(config);new['project_root']=str(root);new['suite_path']=str(remap_path(config['suite_path'],root))
    if config.get('existing_material_path'):new['existing_material_path']=str(remap_path(config['existing_material_path'],root))
    suite=json.loads(Path(new['suite_path']).read_text(encoding='utf-8'))
    manifest=[]
    for doc in suite['documents']:
        path=(Path(new['suite_path']).parent/doc['path']).resolve() if doc.get('path') else Path(new['existing_material_path'])
        manifest.append(dict(document_id=doc['id'],path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),remote_names=doc.get('remote_names',[])))
    old_hashes={d['document_id']:d['sha256'] for d in config['material_manifest']}
    if {d['document_id']:d['sha256'] for d in manifest}!=old_hashes:raise ValueError('材料版本已改变；请建立新的实验条件，不复用旧材料确认')
    new['material_manifest']=manifest;new['selected_tasks']=[];new['selected_products']=list(dict.fromkeys(c['product'] for c in choices));new['selected_runs']=choices
    new['max_runs']=len(choices);new['rerun_of']=str(folder);new['rerun_scope']=scope
    if operation_mode is not None:
        if operation_mode not in ('model','rules'):raise ValueError('未知operation_mode')
        new['operation_mode']=operation_mode
    new.setdefault('operation_mode','model')
    new['max_operation_steps']=80 if new['operation_mode']=='rules' else 12
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    family='public_dataset' if suite['origin']=='public_dataset_adapted' else 'business'
    new['output_dir']=str(root/'evaluation'/f'{family}_runs'/stamp)
    requests=root/'evaluation'/'rerun_requests';requests.mkdir(parents=True,exist_ok=True)
    target=requests/f'{stamp}.json';target.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(planned_runs=len(choices),config_written=True,config_path=str(target),output_dir=new['output_dir'],choices=choices,operation_mode=new['operation_mode'],note='仅准备配置，尚未调用产品；发布/模型/检索条件若已变更需另记新配置')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--scope',choices=['execution_errors','review_failed','unreviewed'],default='execution_errors');p.add_argument('--project-root',default=str(ROOT));p.add_argument('--operation-mode',choices=['rules','model']);a=p.parse_args()
    print(json.dumps(prepare(a.folder,a.scope,a.project_root,a.operation_mode),ensure_ascii=False,indent=2))
