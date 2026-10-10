import unittest
from core import source_clues
from engine import eligible_actions, persona_context, PERSONAS
class SourceChecks(unittest.TestCase):
 def test_coze_excerpt_without_quotes(self):
  clues=source_clues('wl是矢量格式。\n【参考来源】\n[DU002_context.txt] wl是中地公司绘图软件mapgis中矢量格式的线文件。')
  self.assertTrue(clues['excerpt_present']);self.assertEqual(len(clues['visible_source_pairs']),1)
  self.assertFalse(clues['source_verified'])
 def test_name_alone_is_not_excerpt(self):
  self.assertFalse(source_clues('来源：DU002_context.txt')['excerpt_present'])
 def test_named_quote_does_not_force_finish(self):
  self.assertIn('ask_source',eligible_actions(PERSONAS['source_checker'],'DU002_context.txt 原文：这是一段有可能错误归属的引文。',0))
 def test_limit_still_applies(self):
  self.assertEqual(eligible_actions(PERSONAS['source_checker'],'无来源',1),['finish'])
 def test_oracle_stays_hidden(self):
  data=persona_context(PERSONAS['source_checker'],dict(question='问题',scenario='场景',reference_answers=['秘密'],reference_document_ids=['秘密文件']), '回答',0)
  self.assertNotIn('秘密',str(data))
