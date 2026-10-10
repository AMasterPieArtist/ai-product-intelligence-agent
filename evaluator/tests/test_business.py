import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import engine
from core import allowed_actions
from dataset_import import convert
from dataset_metrics import metrics
from runner import plan,matrix_report,material_manifest
from review import validate_review
ROOT=Path(__file__).resolve().parents[1]

def record(answer,status='finished'):
 return dict(agent_status=status,turns=[dict(status='finished',answer_clean=answer)])
class BusinessChecks(unittest.TestCase):
 def setUp(self):self.suite=engine.load_suite(ROOT/'data/business_tasks.json')
 def test_task_specific_checks_and_no_completion_claim(self):
  t=self.suite['tasks'][1]
  self.assertEqual(engine.evaluate(record('支持PDF和TXT'),t)['initial_answer_rule'],'rule_passed')
  self.assertEqual(engine.evaluate(record('支持PDF'),t)['initial_answer_rule'],'failed')
  self.assertEqual(engine.evaluate(record('支持PDF和TXT'),t)['task_completion'],'not_verified')
 def test_negation_cannot_be_unqualified_rule_pass(self):
  self.assertEqual(engine.evaluate(record('不是林晓'),self.suite['tasks'][0])['initial_answer_rule'],'needs_review')
 def test_missing_and_version_answers_need_review(self):
  self.assertEqual(engine.evaluate(record('年度营业收入为2万元'),self.suite['tasks'][3])['initial_answer_rule'],'failed')
  self.assertEqual(engine.evaluate(record('资料没有记录年度营业收入'),self.suite['tasks'][3])['initial_answer_rule'],'needs_review')
  self.assertEqual(engine.evaluate(record('400元，V2'),self.suite['tasks'][4])['initial_answer_rule'],'needs_review')
 def test_failed_execution_not_quality_pass(self):
  self.assertEqual(engine.evaluate(dict(agent_status='error',turns=[]),self.suite['tasks'][0])['initial_answer_rule'],'not_evaluated')
 def test_private_oracle_and_reference_do_not_reach_persona(self):
  t=dict(self.suite['tasks'][0],reference_answers=['SECRET'])
  data=engine.persona_context(engine.PERSONAS['source_checker'],t,'没有给出出处',0)
  self.assertNotIn('oracle',data);self.assertNotIn('SECRET',json.dumps(data));self.assertNotIn('reference_document_ids',data)
 def test_filename_only_still_triggers_source_request(self):
  p=engine.PERSONAS['source_checker']
  self.assertIn('ask_source',engine.eligible_actions(p,'来源 a.txt',0))
  self.assertIn('ask_source',engine.eligible_actions(p,'来源 a.txt；原文：',0))
  self.assertIn('ask_source',engine.eligible_actions(p,'来源 a.txt；原文：项目负责人：林晓',0))  # 来源格式不能代替对应关系判断
  self.assertEqual(engine.eligible_actions(p,'缺少出处',1),['finish'])
 def test_budget_and_registered_adapter(self):
  cfg=dict(selected_products=['dify_app','coze_app'],products={p:dict(name=p,url='https://example.org') for p in ['dify_app','coze_app']},max_runs=32)
  self.assertEqual(len(plan(cfg,self.suite)),28)
  with self.assertRaises(ValueError):plan(dict(cfg,max_runs=3),self.suite)
  with self.assertRaises(ValueError):plan(dict(cfg,selected_products=['arbitrary_web']),self.suite)
 def test_review_needs_evidence_and_real_record(self):
  with self.assertRaises(ValueError):validate_review({'fake':{}},[])
  with self.assertRaises(ValueError):validate_review({'run1':dict(task_completion='passed')},[dict(run_id='run1')])
 def test_pending_matrix_not_fabricated_result(self):
  cfg=dict(selected_products=['dify_app','coze_app'],selected_tasks=['B01'],products={p:dict(name=p,url='https://example.org') for p in ['dify_app','coze_app']},max_runs=32)
  with tempfile.TemporaryDirectory() as tmp:s=matrix_report(tmp,cfg,self.suite,[]).read_text()
  self.assertEqual(s.count('待运行'),4);self.assertIn('待填写',s)
 def test_actual_materials_hashed(self):
  manifest=material_manifest(self.suite)
  self.assertEqual(len(manifest),4);self.assertTrue(all(len(x['sha256'])==64 for x in manifest))
 def test_duplicate_task_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=dict(self.suite);data['tasks']=[self.suite['tasks'][0]]*2
   p=Path(tmp)/'tasks.json';p.write_text(json.dumps(data))
   with self.assertRaises(ValueError):engine.load_suite(p)

class DatasetChecks(unittest.TestCase):
 def test_import_excludes_gold_from_uploaded_document_and_handles_segments(self):
  row=dict(question_id='test-fixture',question='测试问题',answers=['答案不应写进上传资料'],documents=[dict(title='原始文章',segmented_paragraphs=[['文','档','正','文']])])
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'fixture.jsonl';source.write_text(json.dumps(row,ensure_ascii=False)+'\n')
   out=convert(source,Path(tmp)/'imported',1);suite=engine.load_suite(out)
   content=(out.parent/suite['documents'][0]['path']).read_text()
   self.assertNotIn(row['answers'][0],content);self.assertIn('文档正文',content)
   self.assertEqual(suite['selection_review'],'pending');self.assertFalse(suite['tasks'][0]['provenance']['reference_exactly_in_documents'])
 def test_unlabelled_rows_skipped_and_provenance_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'fixture.jsonl';rows=[dict(question='跳过',answers=[],documents=[]),dict(question='问题',answers=['正文'],documents=[dict(paragraphs=['正文'])])]
   source.write_text('\n'.join(json.dumps(r) for r in rows))
   out=convert(source,Path(tmp)/'imported',1);suite=engine.load_suite(out)
   self.assertEqual(suite['tasks'][0]['provenance']['source_line'],2)
   self.assertTrue((out.parent/'import_log.json').exists())
 def test_diagnostics_are_not_semantic_score(self):
  m=metrics('答案是林晓',['林晓']);self.assertEqual(m['lexical_em'],0);self.assertGreater(m['character_f1'],0)
  self.assertEqual(metrics('林晓',['林晓'])['lexical_em'],1)

class PersonaChecks(unittest.IsolatedAsyncioTestCase):
 async def test_followup_adapts_and_reuses_session_bounded(self):
  answers=['负责人是林晓','来源 a.txt；原文：项目负责人：林晓']
  class Model:
   def decide(self,task,data,allowed):return dict(action='ask_source',reason='当前缺少出处')
  async def turn(adapter,model,q,index,save,turns):
   item=dict(turn=index,question=q,status='finished',answer_clean=answers[index-1]);turns.append(item);return item
  suite=engine.load_suite(ROOT/'data/business_tasks.json');r=dict(persona=engine.PERSONAS['source_checker'],task=suite['tasks'][0],question='负责人是谁',turns=[],persona_decisions=[])
  with patch('engine.execute_turn',turn):await engine.orchestrate(object(),Model(),r,lambda:None)
  self.assertEqual(len(r['turns']),2);self.assertEqual(r['agent_status'],'finished');self.assertEqual(r['persona_decisions'][-1]['action'],'finish')
 async def test_quick_persona_never_calls_persona_model(self):
  class Model:
   def decide(self,*a):raise AssertionError('快速用户不需要Persona模型调用')
  async def turn(adapter,model,q,index,save,turns):
   item=dict(turn=index,status='finished',answer_clean='回答');turns.append(item);return item
  suite=engine.load_suite(ROOT/'data/business_tasks.json');r=dict(persona=engine.PERSONAS['quick_lookup'],task=suite['tasks'][0],question='问题',turns=[],persona_decisions=[])
  with patch('engine.execute_turn',turn):await engine.orchestrate(object(),Model(),r,lambda:None)
  self.assertEqual(len(r['turns']),1)
if __name__=='__main__':unittest.main()
