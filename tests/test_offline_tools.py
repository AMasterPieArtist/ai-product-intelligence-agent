import importlib.util,json,tempfile,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
workbench=module('review_workbench');rerun=module('prepare_rerun')
class OfflineReviewChecks(unittest.TestCase):
 def test_hash_mismatch_never_supplies_verified_quote_and_existing_reviews_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'run';d=folder/'r1';d.mkdir(parents=True)
   material=root/'a.txt';material.write_text('引用正文',encoding='utf-8')
   record=dict(run_id='r1',task=dict(reference_answers=['正文'],oracle={},requires_human_review=False),agent_status='finished',turns=[dict(status='finished',answer_clean='来源a.txt，原文“引用正文”')],material_manifest=[dict(document_id='a.txt',path=str(material),sha256='wrong')],evaluation=dict(initial_answer_rule='rule_passed'))
   (d/'record.json').write_text(json.dumps(record));reviews={'r1':dict(task_completion='inconclusive',source_authenticity='inconclusive',reviewer='本人',evidence_note='',user_fit_note='原判断',custom='保留')}
   (folder/'human_reviews.json').write_text(json.dumps(reviews));before=(folder/'human_reviews.json').read_bytes()
   result=workbench.build(folder,root)
   queue=json.loads((folder/'review_queue.json').read_text())
   self.assertEqual(queue[0]['quote_checks'][0]['exact_match_documents'],[])
   self.assertEqual((folder/'human_reviews.json').read_bytes(),before)
   self.assertIn('原判断',(folder/'review_workbench.html').read_text());self.assertFalse(result['human_reviews_changed'])
 def test_untrusted_answer_is_escaped_in_html(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);d=folder/'r';d.mkdir()
   record=dict(run_id='r',task={},agent_status='finished',turns=[dict(status='finished',answer_clean='<script>bad()</script>')],material_manifest=[],evaluation={})
   record['task']={'oracle':{}}
   (d/'record.json').write_text(json.dumps(record));workbench.build(folder,folder)
   output=(folder/'review_workbench.html').read_text()
   self.assertNotIn('<script>bad()</script>',output);self.assertIn('&lt;script&gt;bad()',output)
 def test_empty_error_scope_does_not_create_rerun(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);(folder/'config.json').write_text('{}')
   result=rerun.prepare(folder)
   self.assertEqual(result['planned_runs'],0);self.assertFalse(result['config_written'])

class RerunSelectionChecks(unittest.TestCase):
 def test_only_failed_execution_is_selected_and_material_change_blocks_reuse(self):
  import shutil
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'baseline';folder.mkdir()
   shutil.copytree(ROOT/'evaluator/data',root/'evaluator/data')
   suite=json.loads((root/'evaluator/data/business_tasks.json').read_text())
   manifest=[dict(document_id=d['id'],path=str(root/'evaluator/data'/d['path']),sha256=hashlib.sha256((root/'evaluator/data'/d['path']).read_bytes()).hexdigest(),remote_names=d.get('remote_names',[])) for d in suite['documents']]
   config=dict(suite_path=str(root/'evaluator/data/business_tasks.json'),material_manifest=manifest,products={p:dict(url='https://example.org') for p in ['coze_app','dify_app']})
   (folder/'config.json').write_text(json.dumps(config))
   for rid,status,pid,persona in [('coze_app_B01_source_checker','error','coze_app','source_checker'),('dify_app_B01_quick_lookup','finished','dify_app','quick_lookup')]:
    record=dict(run_id=rid,agent_status=status,product_id=pid,persona_id=persona,task=dict(id='B01'))
    dest=folder/rid;dest.mkdir();(dest/'record.json').write_text(json.dumps(record))
   result=rerun.prepare(folder,project_root=root,operation_mode='rules')
   self.assertEqual(result['choices'],[dict(product='coze_app',task='B01',persona='source_checker')])
   saved=json.loads(Path(result['config_path']).read_text());self.assertEqual(len(saved['selected_runs']),1)
   self.assertFalse(Path(saved['output_dir']).exists())
   material=root/'evaluator/data/materials/project_overview.txt';material.write_text('改变资料')
   with self.assertRaisesRegex(ValueError,'材料版本已改变'):rerun.prepare(folder,project_root=root)


class RelocatedProjectChecks(unittest.TestCase):
 def test_historical_windows_paths_map_to_current_modules(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for old,new in [('day7_dataset','evaluator'),('day6_business','evaluator'),('expanded_validation','benchmarks')]:
    target=root/new/'tasks.json';target.parent.mkdir(exist_ok=True);target.write_text('{}')
    value='D:/github/ai-product-intelligence-agent/'+old+'/tasks.json'
    self.assertEqual(rerun.remap_path(value,root),target.resolve())
 def test_review_resolves_relocated_enterprise_material_by_hash(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);material=root/'benchmarks/materials/EV04_expense_v2.txt'
   material.parent.mkdir(parents=True);material.write_text('fixture source',encoding='utf-8')
   entry=dict(document_id=material.name,path='D:/old/expanded_validation/materials/'+material.name,sha256=hashlib.sha256(material.read_bytes()).hexdigest())
   found=workbench.resolve_material(entry,root)
   self.assertEqual(found['status'],'hash_matched')
   self.assertEqual(found['text'],'fixture source')
