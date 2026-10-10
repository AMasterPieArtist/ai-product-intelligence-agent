"""Sequential web runs across task/persona/product combinations with durable evidence."""
import argparse
import asyncio
import hashlib
import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from adapters import ADAPTERS,COMPLETION_BASES
from adapter_contract import validate_adapter
from core import ModelClient
from engine import PERSONAS,load_suite,orchestrate,evaluate,answer_report
from review import read_reviews,init_reviews
from stability import open_page,batch_outcome

def dump(path,value):
 Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def safe(v):return str(v).replace('|','/').replace('\n',' ')

def plan(config,suite):
 tasks={t['id']:t for t in suite['tasks']}
 selected=config.get('selected_tasks') or list(tasks)
 if len(selected)!=len(set(selected)):raise ValueError('重复选择任务')
 products=config['selected_products']
 if not products or len(products)!=len(set(products)):raise ValueError('产品选择为空或重复')
 for pid in products:
  if pid not in ADAPTERS or pid not in config['products']:raise ValueError('未注册网页Adapter：'+pid)
  if not config['products'][pid]['url'].startswith(('https://','http://')):raise ValueError('产品网址不正确')
  if 'REPLACE_WITH_' in config['products'][pid]['url']:raise ValueError('请填写自己的实际发布应用URL')
 output=[]
 for tid in selected:
  if tid not in tasks:raise ValueError('任务不存在：'+tid)
  t=tasks[tid]
  for persona in t['personas']:
   for pid in products:output.append((pid,persona,t))
 if config.get('operation_mode','model') not in ('model','rules'):raise ValueError('operation_mode应为model或rules')
 if 'selected_runs' in config:
  choices=config['selected_runs']
  if not isinstance(choices,list):raise ValueError('selected_runs应为组合列表')
  bykey={(pid,persona,t['id']):(pid,persona,t) for pid,persona,t in output}
  keys=[]
  for choice in choices:
   key=(choice['product'],choice['persona'],choice['task'])
   if key not in bykey:raise ValueError('重测组合不在当前产品/任务/Persona计划中：'+str(key))
   keys.append(key)
  if len(keys)!=len(set(keys)):raise ValueError('重复选择重测组合')
  output=[bykey[key] for key in keys]
 if len(output)>config.get('max_runs',32):raise ValueError('计划超过max_runs，请减少任务或提高明确预算')
 return output

def material_manifest(suite,external_path=None):
 result=[]
 for doc in suite['documents']:
  path=(Path(suite['_path']).parent/doc['path']).resolve() if doc.get('path') else Path(external_path).resolve() if external_path else None
  if path is None or not path.is_file():raise FileNotFoundError('缺少本地资料：'+str(path))
  result.append(dict(document_id=doc['id'],path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),remote_names=doc.get('remote_names',[])))
 return result

def matrix_report(folder,config,suite,records):
 folder=Path(folder);reviews=read_reviews(folder,records)
 bykey={(r['product_id'],r['task']['id'],r['persona_id']):r for r in records}
 lines=['# 业务需求 × Persona × 产品适配矩阵','',f"任务集：{suite['suite_id']}；材料来源：{suite['origin']}",
 '每格：执行状态 / 首答规则 / 人工任务复核 / 人工来源复核 / 轮数。未运行与未复核不会计为通过。','']
 products=config['selected_products']
 lines+=['| 业务任务 | 用户行为 | '+' | '.join(safe(config['products'][pid]['name']) for pid in products)+' |', '|---|---|'+'---|'*len(products)]
 seen=set()
 for pid,persona,t in plan(config,suite):
  key=(t['id'],persona)
  if key in seen:continue
  seen.add(key);row=[t['id']+' '+t['scenario'],PERSONAS[persona]['name']]
  for product in products:
   r=bykey.get((product,t['id'],persona))
   if not r:row.append('待运行');continue
   rv=reviews.get(r['run_id'],{})
   summary=f"{r['agent_status']} / {r['evaluation']['initial_answer_rule']} / {rv.get('task_completion','not_reviewed')} / {rv.get('source_authenticity','not_reviewed')} / {len(r['turns'])}轮"
   row.append(f"[{summary}]({r['run_id']}/report.md)")
  lines+=['| '+' | '.join(map(safe,row))+' |']
 lines+=['','## 测试条件','']
 for pid in products:
  p=config['products'][pid];lines += [f"- {p['name']}：{p['url']}",f"  配置：{json.dumps(p.get('settings',{}),ensure_ascii=False)}",f"  本轮材料配置确认：{p.get('material_confirmed',False)}（用户确认，不是自动验证远端内容）"]
 lines+=['','## 用量与耗时','', '| 运行ID | 秒 | 决策调用 | 已返回决策tokens |','|---|---:|---:|---:|']
 for r in records:lines += [f"| {r['run_id']} | {r['elapsed_seconds']} | {r['model_calls']} | {r['total_tokens']} |"]
 lines += ['','耗时包含浏览器、决策、产品问答和截图；不等于纯产品响应时间。Tokens仅为测试Agent已返回用量。',
 '本报告没有合成总分、满意度、平台排名或效率提升。计算与版本等任务需要语义复核。','',
 '## 基于证据的用户适配判断','']
 notes=[f"- [{rid}]({rid}/report.md)：{v['user_fit_note']}" for rid,v in reviews.items() if v.get('user_fit_note','').strip()]
 lines += notes or ['待填写 human_reviews.json 中的 user_fit_note，说明具体任务、用户需求与证据支持的结论。']
 target=folder/'matrix.md';target.write_text('\n'.join(lines)+'\n',encoding='utf-8');return target

async def run_one(pw,folder,config,suite,pid,persona,task,key):
 rid=f"{pid}_{task['id']}_{persona}";out=folder/rid;out.mkdir(exist_ok=False)
 record=dict(schema_version='day6-business-v1',run_id=rid,product_id=pid,product=config['products'][pid],
             persona_id=persona,persona=PERSONAS[persona],task=task,question=task['question'],suite_id=suite['suite_id'],
             dataset_origin=suite['origin'],agent_status='running',turns=[],persona_decisions=[],error=None,
             completion_basis=COMPLETION_BASES[pid],browser_events=[],material_manifest=config['material_manifest'],capture_mode='automated',
             operation_mode=config.get('operation_mode','model'),controller_version='state_rules_v1' if config.get('operation_mode')=='rules' else 'model_v1',
             followup_version='topic_v1',snapshot_policy=config.get('snapshot_policy','transitions' if config.get('operation_mode')=='rules' else 'all'),rerun_of=config.get('rerun_of'))
 def save():dump(out/'record.json',record)
 model=ModelClient(key,os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com'),os.getenv('DEEPSEEK_MODEL','deepseek-chat'),max_calls=config.get('max_calls_per_run',26))
 browser=None;page=None;adapter=None;cleanup=False;started=time.monotonic();save()
 def event(name):
  record['browser_events'].append(dict(event=name,phase='cleanup' if cleanup else 'execution',at=datetime.now().astimezone().isoformat()));save()
 try:
  browser=await pw.chromium.launch(headless=config.get('headless',False));browser.on('disconnected',lambda *_:event('browser_disconnected'))
  page=await browser.new_page(viewport={'width':1280,'height':900});page.set_default_timeout(10000)
  page.on('close',lambda *_:event('page_closed'));page.on('crash',lambda *_:event('page_crashed'))
  record['navigation_attempts']=[]
  await open_page(page,record['product']['url'],record['navigation_attempts'],save)
  adapter=ADAPTERS[pid](page,out);validate_adapter(adapter);adapter.operation_mode=config.get('operation_mode','model');adapter.max_operation_steps=config.get('max_operation_steps',80 if adapter.operation_mode=='rules' else 12);adapter.snapshot_policy=record['snapshot_policy'];await adapter.editor.wait_for(state='visible',timeout=30000)
  if await adapter.questions.count() or await adapter.answers.count():raise RuntimeError('需要全新对话，但页面已有消息')
  await orchestrate(adapter,model,record,save)
 except Exception as exc:
  record.update(agent_status='error',error=f'{type(exc).__name__}: {exc}',error_traceback=traceback.format_exc())
  if page and not page.is_closed():
   try:await page.screenshot(path=str(out/'failure.png'),full_page=True,timeout=5000)
   except Exception:pass
 finally:
  if adapter is not None:
   record['input_recovery_events']=getattr(adapter,'input_recovery_events',[])
  cleanup=True
  if browser and browser.is_connected():
   try:await browser.close()
   except Exception as exc:record['cleanup_error']=str(exc)
  record['model_attempts']=getattr(model,'retry_events',[])
  record.update(elapsed_seconds=round(time.monotonic()-started,2),model_calls=model.calls,total_tokens=sum(u.get('total_tokens',0) for u in model.usage),target_tokens=None)
  record['evaluation']=evaluate(record,task);save();dump(out/'evaluation.json',record['evaluation'])
  (out/'report.md').write_text(answer_report(record),encoding='utf-8')
 return record

async def run_batch(config_path):
 config=json.loads(Path(config_path).read_text(encoding='utf-8'))
 config['requested_stop_on_error']=config.get('stop_on_error')
 config['stop_on_error']=False
 print('Batch policy: continue after individual run errors; config:',str(config_path),flush=True)
 suite=load_suite(config['suite_path']);jobs=plan(config,suite)
 if not jobs:raise ValueError('计划为空，不启动浏览器或API')
 if suite['origin']=='public_dataset_adapted' and config.get('dataset_selection_reviewed') is not True:
  raise ValueError('请先人工检查公开样本的资料支持、业务适配和使用条款，确认后设dataset_selection_reviewed=True')
 actual=material_manifest(suite,config.get('existing_material_path'))
 if actual!=config.get('material_manifest'):raise ValueError('资料已变更，请重新运行Notebook配置格建立实验')
 for pid in config['selected_products']:
  if config['products'][pid].get('material_confirmed') is not True:raise ValueError('请先确认每个产品已配置本轮资料，再设material_confirmed=True')
 folder=Path(config['output_dir']);folder.mkdir(parents=True,exist_ok=False)
 dump(folder/'config.json',config);dump(folder/'task_suite.json',suite)
 status=dict(status='running',planned_runs=len(jobs),completed_runs=0,attempted_runs=0,successful_runs=0,failed_runs=0,current=None,error=None);records=[]
 def save():dump(folder/'batch_status.json',status);matrix_report(folder,config,suite,records)
 save()
 try:
  from dotenv import load_dotenv
  from playwright.async_api import async_playwright
  load_dotenv(Path(config['project_root'])/'.env',override=True);key=os.getenv('DEEPSEEK_API_KEY')
  if not key:raise RuntimeError('项目.env缺少DEEPSEEK_API_KEY')
  async with async_playwright() as pw:
   for pid,persona,task in jobs:
    status['current']=f"{pid}_{task['id']}_{persona}";save();print('Starting:',status['current'],flush=True)
    record=await run_one(pw,folder,config,suite,pid,persona,task,key);records.append(record)
    status.update(completed_runs=len(records),attempted_runs=len(records),
                  successful_runs=sum(r['agent_status']=='finished' for r in records),
                  failed_runs=sum(r['agent_status']!='finished' for r in records))
    save();print(record['run_id'],record['agent_status'],flush=True)
    if record['agent_status']!='finished' and config.get('stop_on_error',False):break
  status.update(batch_outcome(records,len(jobs)))
 except Exception as exc:status.update(status='error',error=f'{type(exc).__name__}: {exc}',error_traceback=traceback.format_exc())
 finally:
  status['current']=None;save();init_reviews(folder);print('Saved:',folder/'matrix.md',flush=True)
 return 0 if status['status']=='finished' else 1

def rebuild(folder):
 folder=Path(folder);config=json.loads((folder/'config.json').read_text(encoding='utf-8'));suite=json.loads((folder/'task_suite.json').read_text(encoding='utf-8'))
 records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*/record.json'))]
 init_reviews(folder);return matrix_report(folder,config,suite,records)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--config');ap.add_argument('--rebuild');ap.add_argument('--plan');args=ap.parse_args()
 if args.plan:
  cfg=json.loads(Path(args.plan).read_text(encoding='utf-8'));suite=load_suite(cfg['suite_path']);jobs=plan(cfg,suite)
  upper=sum(min(cfg.get('max_calls_per_run',26),PERSONAS[u]['max_followups']) for _,u,_ in jobs) if cfg.get('operation_mode')=='rules' else len(jobs)*cfg.get('max_calls_per_run',26)
  print(json.dumps(dict(planned_runs=len(jobs),operation_mode=cfg.get('operation_mode','model'),max_decision_calls=upper,jobs=[dict(product=p,persona=u,task=t['id']) for p,u,t in jobs]),ensure_ascii=False,indent=2))
 elif args.rebuild:print(rebuild(args.rebuild))
 elif args.config:raise SystemExit(asyncio.run(run_batch(args.config)))
 else:ap.error('需要--config或--rebuild')
