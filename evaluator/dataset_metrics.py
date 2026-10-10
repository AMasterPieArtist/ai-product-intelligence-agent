"""Transparent lexical diagnostics. Not the official DuReader evaluation script."""
import re
from collections import Counter

def norm(s):return re.sub(r'[\W_]+','',s).lower()
def metrics(answer,references):
 a=norm(answer);refs=[norm(x) for x in references if norm(x)]
 if not refs:return {'lexical_em':None,'character_f1':None}
 def f1(b):
  overlap=sum((Counter(a)&Counter(b)).values())
  if not a or not b or not overlap:return 0.0
  p=overlap/len(a);r=overlap/len(b);return 2*p*r/(p+r)
 return dict(lexical_em=float(a in refs),character_f1=round(max(f1(b) for b in refs),4),
             method='normalised_character_overlap_not_official_dureader',note='解释性长答会降低分数，错误陈述也可能有高重合；仅辅助复核，不能代替业务完成判断。')
