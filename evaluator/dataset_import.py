"""Convert locally obtained DuReader JSONL to grounded tasks. Does not download data.

Supports question/answers/documents with paragraphs or segmented_paragraphs.
Rows without reference answers or usable document text are skipped explicitly.
Public data must be manually checked for task fit, answer support and usage terms.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

def text_of(doc):
 paragraphs=doc.get('paragraphs')
 if not paragraphs:paragraphs=doc.get('segmented_paragraphs')
 if not isinstance(paragraphs,list):return ''
 return '\n'.join(''.join(p) if isinstance(p,list) else p for p in paragraphs if isinstance(p,(str,list)))

def convert(source,out,limit=5):
 source=Path(source);out=Path(out)
 if not 1<=limit<=50:raise ValueError('limit应为1到50')
 if out.exists():raise FileExistsError('保留原导入记录，请使用新的输出目录')
 # Incremental source hashing and input parsing; do not load full corpora in memory.
 digest=hashlib.sha256()
 with source.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
 out.mkdir(parents=True);(out/'materials').mkdir()
 tasks=[];documents=[];skipped=[];seen=set()
 with source.open(encoding='utf-8-sig') as f:
  for lineno,line in enumerate(f,1):
   if not line.strip():continue
   try:row=json.loads(line)
   except json.JSONDecodeError:skipped.append(dict(line=lineno,reason='invalid_json'));continue
   q=row.get('question');answers=row.get('answers')
   if not isinstance(q,str) or not q.strip() or not isinstance(answers,list):skipped.append(dict(line=lineno,reason='missing_question_or_answers'));continue
   answers=[a for a in answers if isinstance(a,str) and a.strip()]
   if not answers:skipped.append(dict(line=lineno,reason='unlabelled_row'));continue
   if q in seen:skipped.append(dict(line=lineno,reason='duplicate_question'));continue
   passages=[]
   for d in row.get('documents',[]):
    body=text_of(d)
    if body.strip():passages.append((str(d.get('title','未提供标题')),body))
   if not passages:skipped.append(dict(line=lineno,reason='no_document_text'));continue
   seen.add(q);tid=f'DU{len(tasks)+1:03d}';name=tid+'_documents.txt'
   # Include documents, not annotated answers, in remote knowledge.
   body='\n\n'.join(f'原始文档{i+1} 标题：{title}\n{text}' for i,(title,text) in enumerate(passages))
   (out/'materials'/name).write_text(f'导入文件名称：{name}\n'+body,encoding='utf-8')
   documents.append(dict(id=name,path='materials/'+name,remote_names=[name]))
   tasks.append(dict(id=tid,scenario='公开语料文档问答',question=q,personas=['quick_lookup','source_checker'],kind='dataset_qa',requires_human_review=True,
                    oracle=dict(required_groups=[],forbidden_phrases=[],expect_uncertainty=False),reference_answers=answers,reference_document_ids=[name],
                    provenance=dict(source_dataset='DuReader',original_question_id=str(row.get('question_id','')),source_line=lineno,
                                    reference_exactly_in_documents=any(a in body for a in answers))))
   if len(tasks)>=limit:break
 if not tasks:raise ValueError('未找到有效样本；查看原始JSONL是否包含answers和documents')
 suite=dict(suite_id='dureader_subset',origin='public_dataset_adapted',description='DuReader小样本：需人工确认资料支持、场景适配与使用条款；不代表完整数据集评测。',
            source_url='https://github.com/baidu/DuReader',source_file_sha256=digest.hexdigest(),selection_method=f'文件顺序取前{limit}条有效样本；可能有顺序偏差',selection_review='pending',documents=documents,tasks=tasks)
 (out/'tasks.json').write_text(json.dumps(suite,ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'import_log.json').write_text(json.dumps(dict(imported=len(tasks),skipped=skipped),ensure_ascii=False,indent=2),encoding='utf-8')
 return out/'tasks.json'
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--limit',type=int,default=5);args=ap.parse_args()
 print(convert(args.input,args.output,args.limit))
