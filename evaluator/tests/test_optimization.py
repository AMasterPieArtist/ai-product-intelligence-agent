import unittest
from pathlib import Path
from browser_runtime import execute_turn, rule_decision
from engine import load_suite, make_followup
from runner import plan

class FakeAdapter:
    operation_mode='rules'
    def __init__(self):self.filled=False;self.submitted=False;self.ready=False;self.sent=0;self.ended=False
    async def begin(self,q,index):self.question=q
    async def observe(self):return dict(input_ready=True,question_filled=self.filled,send_enabled=self.filled,submitted=self.submitted,answer_ready=self.ready,blocked=False,answer_raw='已观察到的回答' if self.ready else '')
    async def execute(self,action):
        if action=='fill_question':self.filled=True
        elif action=='click_send':self.sent+=1;self.submitted=True
        elif action=='wait':self.ready=True
        return await self.observe()
    async def snapshot(self,label):return {}
    def end(self):self.ended=True
class SpyModel:
    def __init__(self):self.calls=0
    def decide(self,task,data,allowed):
        self.calls+=1
        return dict(action=next(a for a in ('finish','click_send','fill_question','wait') if a in allowed),reason='模拟决定')
class RuleControllerChecks(unittest.IsolatedAsyncioTestCase):
    async def test_rules_preserve_observed_answer_and_submit_once_without_model(self):
        adapter=FakeAdapter();model=SpyModel();turns=[]
        result=await execute_turn(adapter,model,'问题',1,lambda:None,turns)
        self.assertEqual(model.calls,0);self.assertEqual(adapter.sent,1)
        self.assertEqual(result['answer_clean'],'已观察到的回答');self.assertTrue(adapter.ended)
        self.assertTrue(all(h['decision_mode']=='rule' for h in result['history']))
    async def test_model_baseline_is_available(self):
        adapter=FakeAdapter();adapter.operation_mode='model';model=SpyModel()
        result=await execute_turn(adapter,model,'问题',1,lambda:None,[])
        self.assertEqual(result['status'],'finished');self.assertEqual(model.calls,4)
    async def test_uncertain_click_is_never_retried(self):
        class Broken(FakeAdapter):
            async def execute(self,action):
                if action=='click_send':self.sent+=1;raise RuntimeError('uncertain transport')
                return await super().execute(action)
        adapter=Broken();turns=[]
        with self.assertRaisesRegex(RuntimeError,'uncertain transport'):
            await execute_turn(adapter,SpyModel(),'问题',1,lambda:None,turns)
        self.assertEqual(adapter.sent,1);self.assertEqual(turns[0]['status'],'error');self.assertTrue(adapter.ended)
    async def test_rule_wait_budget_is_bounded(self):
        class Stuck(FakeAdapter):
            async def execute(self,action):return await self.observe()
        with self.assertRaisesRegex(RuntimeError,'turn_step_limit'):
            await execute_turn(Stuck(),SpyModel(),'问题',1,lambda:None,[],max_steps=2)
class ExactSelectionChecks(unittest.TestCase):
    def setUp(self):
        self.suite=load_suite(Path(__file__).resolve().parents[1]/'data/business_tasks.json')
        self.cfg=dict(selected_products=['dify_app','coze_app'],products={p:dict(url='https://example.org') for p in ('dify_app','coze_app')},max_runs=32)
    def test_exact_rerun_does_not_expand_personas_or_products(self):
        choice=dict(product='coze_app',task='B01',persona='source_checker')
        jobs=plan(dict(self.cfg,selected_runs=[choice]),self.suite)
        self.assertEqual([(p,u,t['id']) for p,u,t in jobs],[('coze_app','source_checker','B01')])
    def test_duplicate_and_invalid_reruns_rejected(self):
        choice=dict(product='coze_app',task='B01',persona='source_checker')
        with self.assertRaises(ValueError):plan(dict(self.cfg,selected_runs=[choice,choice]),self.suite)
        with self.assertRaises(ValueError):plan(dict(self.cfg,selected_runs=[dict(choice,persona='newcomer')]),self.suite)
    def test_empty_selected_runs_do_not_default_to_all(self):
        self.assertEqual(plan(dict(self.cfg,selected_runs=[]),self.suite),[])
    def test_followup_retains_question_and_has_no_reference_answer(self):
        text=make_followup('项目负责人是谁？','ask_source')
        self.assertIn('项目负责人是谁？',text);self.assertNotIn('林晓',text)

class EvidenceCaptureChecks(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_wait_keeps_final_capture_and_full_action_history(self):
        class Slow(FakeAdapter):
            def __init__(self):super().__init__();self.waits=0;self.snapshots=[]
            async def execute(self,action):
                if action=='wait':self.waits+=1;self.ready=self.waits>=3;return await self.observe()
                return await super().execute(action)
            async def snapshot(self,label):self.snapshots.append(label);return {'screenshot':label+'.png'}
        adapter=Slow();result=await execute_turn(adapter,SpyModel(),'问题',1,lambda:None,[])
        self.assertEqual(len(result['history']),6);self.assertEqual(len(adapter.snapshots),4)
        self.assertEqual(sum(bool(h['artifacts'].get('skipped')) for h in result['history']),2)
        self.assertIn('screenshot',result['history'][-1]['artifacts'])
