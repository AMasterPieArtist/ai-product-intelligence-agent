import unittest
import engine
from verify_dataset import verify
from runner import plan
from pathlib import Path
@unittest.skipUnless((Path(__file__).resolve().parents[1]/'dataset/raw/dev.json').is_file(), '先执行tools/prepare_public_dataset.py准备公开数据')
class PublicDatasetChecks(unittest.TestCase):
 def test_provenance_and_upload_materials_are_exact(self):
  self.assertEqual(verify()['prepared_tasks'],5)
 def test_smaller_default_and_full_plan(self):
  suite=engine.load_suite(Path(__file__).resolve().parents[1]/'dataset/tasks.json')
  cfg=dict(selected_tasks=['DU001'],selected_products=['dify_app','coze_app'],products={p:dict(url='https://example.org') for p in ['dify_app','coze_app']},max_runs=4)
  self.assertEqual(len(plan(cfg,suite)),4)
  self.assertEqual(len(plan(dict(cfg,selected_tasks=[],max_runs=20),suite)),20)
 def test_followup_keeps_topic_without_gold(self):
  question='请根据资料说明qsv是什么格式'
  text=engine.make_followup(question,'ask_source')
  self.assertIn(question,text);self.assertNotIn('视频格式',text)
