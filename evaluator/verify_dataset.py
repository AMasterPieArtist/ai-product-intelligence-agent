"""Offline integrity and exact-span checks. No network, model or browser use."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).parent

def verify():
 base=ROOT/'dataset';manifest=json.loads((base/'download_manifest.json').read_text(encoding='utf-8'))
 raw=base/'raw';source=json.loads((raw/'dev.json').read_text(encoding='utf-8'))
 for name,key in [('dev.json','dev_sha256'),('dureader_robust-data.tar.gz','archive_sha256')]:
  assert hashlib.sha256((raw/name).read_bytes()).hexdigest()==manifest[key], 'Original file hash changed: '+name
 with tarfile.open(raw/'dureader_robust-data.tar.gz') as tf:
  assert tf.extractfile('dureader_robust-data/dev.json').read()==(raw/'dev.json').read_bytes()
 suite=json.loads((base/'tasks.json').read_text(encoding='utf-8'));review=json.loads((base/'sample_review.json').read_text(encoding='utf-8'))
 byreview={r['task_id']:r for r in review}
 for task in suite['tasks']:
  p=task['provenance'];paragraph=source['data'][p['source_data_index']]['paragraphs'][p['source_paragraph_index']]
  qa=next(q for q in paragraph['qas'] if q['id']==p['original_question_id']);context=paragraph['context']
  assert qa['question']==p['original_question']
  assert task['reference_answers']==list(dict.fromkeys(a['text'] for a in qa['answers']))
  assert all(a in context for a in task['reference_answers'])
  material=base/'materials'/task['reference_document_ids'][0]
  expected=f"文档名称：{material.name}\n资料来源：DuReader-robust dev；样本ID：{qa['id']}\n"+context+'\n'
  assert material.read_text(encoding='utf-8')==expected, 'Upload must contain context and identifying header only'
  assert hashlib.sha256(material.read_bytes()).hexdigest()==byreview[task['id']]['material_sha256']
  for a in p['answer_spans']:
   assert context[a['computed_context_start']:a['computed_context_end']]==a['text']
   assert a['original_answer_start']==next(x['answer_start'] for x in qa['answers'] if x['text']==a['text'])
 return dict(dataset=suite['suite_id'],prepared_tasks=len(suite['tasks']),reference_span_check='passed',product_evaluation='not_run',source_authenticity='not_evaluated')
if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
