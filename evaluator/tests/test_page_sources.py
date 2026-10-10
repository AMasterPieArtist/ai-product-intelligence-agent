import unittest
from unittest.mock import patch
from adapters import DifySourceBrowser, ADAPTERS
from engine import orchestrate, PERSONAS
from core import source_clues

class FakeAnswers:
    def __init__(self, captured, count=1):
        self.captured=captured;self.total=count;self.requested=[]
    async def count(self):return self.total
    def nth(self,index):self.requested.append(index);return self
    async def evaluate(self,script):return self.captured

class CardCaptureChecks(unittest.IsolatedAsyncioTestCase):
    def adapter(self,captured,count=1,a0=0):
        a=object.__new__(DifySourceBrowser);a.a0=a0
        a.answers=FakeAnswers(captured,count);return a
    async def test_visible_names_deduplicated_without_fabricating_excerpt(self):
        a=self.adapter(dict(found=True,citation_text='DU002_context.txt\nDU001_context.txt\nDU002_context.txt'))
        result=await a.collect_source_cards()
        self.assertEqual(result['status'],'captured')
        self.assertEqual(len(result['cards']),2)
        self.assertTrue(all(c['excerpt'] is None and not c['expanded'] for c in result['cards']))
        self.assertFalse(result['source_verified'])
    async def test_capture_missing_is_not_product_missing(self):
        a=self.adapter(dict(found=False,citation_text=''))
        self.assertEqual((await a.collect_source_cards())['status'],'not_captured')
    async def test_current_turn_index_not_previous_reply(self):
        a=self.adapter(dict(found=True,citation_text='current.txt'),count=2,a0=1)
        result=await a.collect_source_cards()
        self.assertEqual(a.answers.requested,[1]);self.assertEqual(result['cards'][0]['document_name'],'current.txt')
    async def test_unbalanced_count_does_not_capture(self):
        a=self.adapter(dict(found=True,citation_text='old.txt'),count=3)
        self.assertEqual((await a.collect_source_cards())['status'],'not_captured')
        self.assertEqual(a.answers.requested,[])

class FormattingChecks(unittest.TestCase):
    def test_numbered_source_pair(self):
        c=source_clues('【参考来源】\n1. DU005_context.txt：硫的最高价氧化物为三氧化硫，其中硫呈正六价。')
        self.assertTrue(c['excerpt_present']);self.assertEqual(c['visible_source_pairs'][0]['document_name'],'DU005_context.txt')
        self.assertFalse(c['source_verified'])
    def test_bare_filename_does_not_create_excerpt(self):
        self.assertFalse(source_clues('1. DU005_context.txt')['excerpt_present'])
    def test_registered_adapter(self):self.assertIs(ADAPTERS['dify_app'],DifySourceBrowser)

class DecisionFlowChecks(unittest.IsolatedAsyncioTestCase):
    async def run_case(self,fail=False):
        class Adapter:
            async def collect_source_cards(self):
                if fail:raise RuntimeError('selector broke')
                return dict(status='captured',cards=[dict(document_name='actual.txt',excerpt=None,expanded=False)])
        class Model:
            def decide(self,kind,data,allowed):
                self.data=data
                return dict(action='finish',reason='检查可见信息后结束，真实性另行复核')
        record=dict(question='问题',task=dict(question='问题',scenario='场景',reference_answers=['SECRET']),persona=PERSONAS['source_checker'],turns=[],persona_decisions=[])
        async def turn(adapter,model,question,index,save,turns):
            value=dict(answer_clean='正文',status='finished');turns.append(value);return value
        model=Model()
        with patch('engine.execute_turn',turn):await orchestrate(Adapter(),model,record,lambda:None)
        self.assertEqual(record['turns'][0]['page_sources'],model.data['page_sources'])
        self.assertEqual(record['persona_decisions'][0]['decision_input'],model.data)
        self.assertNotIn('SECRET',str(model.data))
        return record
    async def test_capture_reaches_persona_and_record(self):
        record=await self.run_case();self.assertEqual(record['turns'][0]['page_sources']['status'],'captured')
    async def test_capture_error_preserved_and_decision_continues(self):
        record=await self.run_case(True);self.assertEqual(record['turns'][0]['page_sources']['status'],'capture_error')
        self.assertEqual(record['agent_status'],'finished')
