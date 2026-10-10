"""Human review is an evidence layer, not a silent override of automatic rules."""
import json
from pathlib import Path
ALLOWED={'not_reviewed','passed','failed','inconclusive'}
def validate_review(review,records):
 known={r['run_id'] for r in records}
 for rid,item in review.items():
  if rid not in known:raise ValueError('复核引用不存在的run_id：'+rid)
  for field in ('task_completion','source_authenticity'):
   value=item.get(field,'not_reviewed')
   if value not in ALLOWED:raise ValueError('复核状态无效：'+field)
   if value in {'passed','failed'} and (not item.get('reviewer','').strip() or not item.get('evidence_note','').strip()):
    raise ValueError('通过/失败判断需填写复核人和证据定位')
 return review

def read_reviews(folder,records):
 p=Path(folder)/'human_reviews.json'
 return validate_review(json.loads(p.read_text(encoding='utf-8')),records) if p.exists() else {}

def init_reviews(folder):
 folder=Path(folder);records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*/record.json'))]
 target=folder/'human_reviews.json'
 if target.exists():return target
 review={r['run_id']:dict(task_completion='not_reviewed',source_authenticity='not_reviewed',reviewer='',evidence_note='',user_fit_note='') for r in records}
 target.write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8');return target
