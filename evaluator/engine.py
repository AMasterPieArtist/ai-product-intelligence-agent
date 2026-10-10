"""Task-aware persona orchestration; reference answers never enter browser/model decisions."""
import asyncio
import json
import re
from pathlib import Path
from core import clean_answer, normalize, source_clues
from browser_runtime import execute_turn

PERSONAS=json.loads((Path(__file__).parent/'data/personas.json').read_text(encoding='utf-8'))
FOLLOWUPS={
 'ask_source':'请提供刚才结论来自的文档名称和支持它的原文片段。如果无法提供，请明确说明，不要编造。',
 'ask_clarify':'我不熟悉这些业务术语。请用通俗的话解释，并明确我下一步应该做什么；没有依据的步骤请说明。',
 'challenge':'请重新核对刚才答案的资料依据、版本日期和适用条件。如有冲突或资料不足，请指出，不要猜测。'}

def make_followup(original_question, action):
 return f'针对原问题“{original_question}”，' + FOLLOWUPS[action]


def load_suite(path):
 path=Path(path).resolve();suite=json.loads(path.read_text(encoding='utf-8'))
 if not suite.get('tasks'): raise ValueError('任务集不能为空')
 ids=[t['id'] for t in suite['tasks']]
 if len(ids)!=len(set(ids)):raise ValueError('任务ID重复')
 for t in suite['tasks']:
  if not re.fullmatch(r'[A-Za-z0-9_-]+',t['id']):raise ValueError('任务ID只能包含字母、数字、下划线与短横线')
  if not str(t.get('question','')).strip():raise ValueError('任务问题为空')
  if not t['personas'] or len(t['personas'])!=len(set(t['personas'])):raise ValueError('Persona为空或重复')
  if any(p not in PERSONAS for p in t['personas']):raise ValueError('未知Persona')
  for group in t['oracle']['required_groups']:
   if not group or not all(isinstance(x,str) and x for x in group):raise ValueError('答案约束必须为非空字符串组')
 suite['_path']=str(path)
 return suite

def persona_context(persona,task,answer,used,page_sources=None):
 # Safe user-facing task fields only. Do not expose oracle, expected docs or answers.
 return dict(persona=persona,question=task['question'],scenario=task['scenario'],
             answer=answer,source_clues=source_clues(answer),followups_used=used,
             page_sources=page_sources if page_sources is not None else dict(status="not_collected",cards=[]))

def eligible_actions(persona,answer,used):
 allowed=['finish']
 if used>=persona['max_followups']:return allowed
 # Let the persona assess source mapping/conflicts; formatting cannot prove completion.
 for action in persona['actions']:
  if action not in allowed:allowed.append(action)
 return allowed

async def orchestrate(adapter,model,record,save):
 used=0;question=record['question'];persona=record['persona']
 while True:
  turn=await execute_turn(adapter,model,question,len(record['turns'])+1,save,record['turns'])
  page_sources=dict(status='not_collected',cards=[],source_verified=False)
  if callable(getattr(adapter,'collect_source_cards',None)):
   try:
    page_sources=await adapter.collect_source_cards()
   except Exception as exc:
    page_sources=dict(status='capture_error',cards=[],source_verified=False,
                      error=type(exc).__name__,note='采集失败，不代表页面没有来源。')
  turn['page_sources']=page_sources;save()
  allowed=eligible_actions(persona,turn['answer_clean'],used)
  if allowed==['finish']:
   d=dict(action='finish',reason='行为规则与追问上限允许结束；任务正确性另行评估。',decision_mode='rule')
  else:
   context=persona_context(persona,record['task'],turn['answer_clean'],used,page_sources)
   d=await asyncio.to_thread(model.decide,'persona',context,allowed)
   d['decision_input']=context
   d['allowed_actions']=allowed
  d['persona_version']='page_sources_v3'
  record['persona_decisions'].append(d);save()
  if d['action']=='finish':record['agent_status']='finished';return
  used+=1;question=make_followup(record['question'],d['action'])

UNCERTAIN=('无法确定','无法提供','未提供','未记录','没有记录','没有提供','未提及','无法从','未检索','无相关','没有相关','不知道','资料不足','不能确定','不能确认','无法确认','未找到','没有找到')
RISK=('可能','不一定','并非','不是','更正','有误','无法确定','不能确定','无法确认')
def evaluate(record,task):
 turns=[t for t in record.get('turns',[]) if t.get('status')=='finished']
 first=clean_answer(turns[0].get('answer_clean') or turns[0].get('answer_raw') or '') if turns else ''
 latest=clean_answer(turns[-1].get('answer_clean') or turns[-1].get('answer_raw') or '') if turns else ''
 oracle=task['oracle'];missing=[g for g in oracle['required_groups'] if not any(x in first for x in g)]
 forbidden=[x for x in oracle.get('forbidden_phrases',[]) if x in first]
 uncertainty=any(x in first for x in UNCERTAIN)
 if not turns:check='not_evaluated'
 elif missing or forbidden:check='failed'
 elif oracle.get('expect_uncertainty') and not uncertainty:check='failed'
 elif task.get('requires_human_review') or any(x in first for x in RISK):check='needs_review'
 else:check='rule_passed'
 result=dict(method='task_constraints_v1',execution_status=record['agent_status'],
             initial_answer_rule=check,missing_groups=missing,forbidden_hits=forbidden,
             latest_source_clues=source_clues(latest),source_authenticity='not_verified',
             task_completion='not_verified',note='词语命中仅筛查，否定、计算、版本和语义需人工复核；执行结束不表示完成业务任务。')
 if task.get('reference_answers'):
  from dataset_metrics import metrics
  result['dataset_lexical_diagnostics']=metrics(first,task['reference_answers'])
 return result

def answer_report(record):
 lines=['# 单次业务体验记录','',f"任务：{record['task']['id']} / {record['task']['scenario']}",
 f"用户行为：{record['persona']['name']}",f"执行：{record['agent_status']}",f"首答规则：{record['evaluation']['initial_answer_rule']}",'']
 for t in record['turns']:lines += [f"## 第{t['turn']}轮",t['question'],'',t.get('answer_clean') or '未获得完整回答','']
 lines += ['## 用户行为决策']+[f"- {d['action']}：{d['reason']}" for d in record['persona_decisions']]
 lines += ['','原始页面截图、动作与用量见 record.json。引用真实性须另外复核。']
 return '\n'.join(lines)+'\n'
