"""Summarize recorded costs only; no extrapolated savings or target-product usage."""
import argparse,json
from pathlib import Path

def summarize(folder):
    records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(Path(folder).glob('*/record.json'))]
    rows=[]
    for r in records:
        operation_tokens=sum(h.get('usage',{}).get('total_tokens',0) for t in r.get('turns',[]) for h in t.get('history',[]))
        persona_tokens=sum(d.get('usage',{}).get('total_tokens',0) for d in r.get('persona_decisions',[]))
        rows.append(dict(run_id=r['run_id'],operation_mode=r.get('operation_mode','legacy_model'),execution=r.get('agent_status'),model_calls=r.get('model_calls',0),returned_agent_tokens=r.get('total_tokens',0),returned_operation_tokens=operation_tokens,returned_persona_tokens=persona_tokens,unclassified_returned_tokens=r.get('total_tokens',0)-operation_tokens-persona_tokens,elapsed_seconds=r.get('elapsed_seconds'),review_seconds=None))
    reviews_path=Path(folder)/'human_reviews.json'
    if reviews_path.is_file():
        reviews=json.loads(reviews_path.read_text(encoding='utf-8'))
        for row in rows:row['review_seconds']=reviews.get(row['run_id'],{}).get('review_seconds')
    return dict(runs=rows,total_model_calls=sum(r['model_calls'] for r in rows),total_returned_agent_tokens=sum(r['returned_agent_tokens'] for r in rows),target_product_tokens=None,note='仅已记录/已返回用量；耗时包含浏览器和截图。复核时长若有，是表单经过时间估计。跨轮配置未受控时不能据此声明效率提升。')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');a=p.parse_args();print(json.dumps(summarize(a.folder),ensure_ascii=False,indent=2))
