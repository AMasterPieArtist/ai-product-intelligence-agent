"""Calculate metrics only for actually completed and independently reviewed pairs."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def metrics():
    data=json.loads((HERE/'human_comparison.json').read_text(encoding='utf-8'));paired=[]
    for r in data['records']:
        sides=[r[x] for x in ['human','agent']]
        if not all(s.get('status')=='finished' and isinstance(s.get('active_seconds'),(int,float)) and not isinstance(s['active_seconds'],bool) and s['active_seconds']>=0 for s in sides):continue
        paired.append(r)
    report=dict(time_pairs=len(paired),time_total_pairs=len(data['records']),human_active_seconds=None,agent_active_seconds=None,active_time_saving_fraction=None)
    if paired:
        h=sum(r['human']['active_seconds'] for r in paired);a=sum(r['agent']['active_seconds'] for r in paired)
        report.update(human_active_seconds=h,agent_active_seconds=a,active_time_saving_fraction=(h-a)/h if h>0 else None)
    quality=json.loads((HERE/'quality_comparison.json').read_text(encoding='utf-8'))
    for dimension in ['task','source']:
        counts=dict(tp=0,fp=0,fn=0,tn=0,excluded=0)
        for r in quality['records']:
            g=r['gold_'+dimension];a=r['assisted_'+dimension]
            if not r.get('frozen_evidence_path') or not r.get('gold_reviewer') or not r.get('assisted_reviewer') or g not in ['passed','failed'] or a not in ['passed','failed']:
                counts['excluded']+=1;continue
            key='tp' if g==a=='failed' else 'fp' if a=='failed' else 'fn' if g=='failed' else 'tn'
            counts[key]+=1
        tp,fp,fn=counts['tp'],counts['fp'],counts['fn']
        report[dimension+'_issue_detection']=dict(**counts,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)
    report['note']='无合格样本或分母为0时显示null；inconclusive及未复核单独排除并计数。结果是本小样本辅助流程的表现，不是通用模型正确率。'
    return report
if __name__=='__main__':print(json.dumps(metrics(),ensure_ascii=False,indent=2))
