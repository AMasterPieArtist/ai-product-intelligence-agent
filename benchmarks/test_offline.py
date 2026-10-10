"""No API or browser use. Run: python benchmarks/test_offline.py"""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import prepare
import compare_metrics

class OfflineChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ['stability.py','runner.py','adapters.py','engine.py','core.py','browser_runtime.py','review.py','data/personas.json']:
            p=self.root/'evaluator'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('offline fixture')
        s=prepare.read(prepare.HERE/'app_settings.example.json')
        for product in s['products'].values():product['url']='https://example.org';product['material_confirmed']=True;product['settings']={'model':'fixture','knowledge_scope':'eight files'}
        self.settings=self.root/'settings.json';prepare.write(self.settings,s)
    def tearDown(self):self.tmp.cleanup()
    def plan(self,batch='smoke',campaign='test'):
        return prepare.prepare(self.root,campaign,batch,'rules',self.settings)
    def complete(self,plan):
        cfg=prepare.read(plan['config_path'])
        for j in cfg['selected_runs']:
            rid=f"{j['product']}_{j['task']}_{j['persona']}"
            prepare.write(Path(cfg['output_dir'])/rid/'record.json',dict(run_id=rid,agent_status='finished',product_id=j['product'],task={'id':j['task']},persona_id=j['persona']))
    def test_all_192_unique_and_balanced_with_resume(self):
        first=self.plan();self.assertEqual(first['planned_runs'],8);self.complete(first)
        self.assertEqual(self.plan()['planned_runs'],0)
        total=8
        for batch in map(str,range(1,7)):
            plan=self.plan(batch);total+=plan['planned_runs'];self.complete(plan)
        self.assertEqual(total,192)
        self.assertEqual(self.plan('1')['planned_runs'],0)
    def test_no_full_batch_before_smoke(self):
        with self.assertRaises(ValueError):self.plan('1')
    def test_changed_code_requires_new_campaign(self):
        self.plan();(self.root/'evaluator/core.py').write_text('changed')
        with self.assertRaises(ValueError):self.plan()
    def test_control_groups_are_16_distinct(self):
        a=self.plan('human_first','control');b=self.plan('agent_first','control')
        self.assertEqual(a['planned_runs'],8);self.assertEqual(b['planned_runs'],8)
        ja=prepare.read(a['config_path'])['selected_runs'];jb=prepare.read(b['config_path'])['selected_runs']
        self.assertEqual(len({(j['task'],j['persona'],j['product']) for j in ja+jb}),16)
    def test_unknown_metrics_are_not_zero(self):
        r=compare_metrics.metrics();self.assertIsNone(r['active_time_saving_fraction']);self.assertEqual(r['time_pairs'],0)
        self.assertIsNone(r['task_issue_detection']['precision'])
    def test_metrics_known_confusion_matrix(self):
        prepare.write(self.root/'human_comparison.json',dict(records=[dict(human=dict(status='finished',active_seconds=100),agent=dict(status='finished',active_seconds=60))]))
        rs=[]
        for g,a in [('failed','failed'),('passed','failed'),('failed','passed'),('passed','passed')]:
            rs.append(dict(frozen_evidence_path='fixed',gold_reviewer='A',assisted_reviewer='B',gold_task=g,assisted_task=a,gold_source=g,assisted_source=a))
        prepare.write(self.root/'quality_comparison.json',dict(records=rs))
        with patch.object(compare_metrics,'HERE',self.root):r=compare_metrics.metrics()
        self.assertEqual(r['active_time_saving_fraction'],0.4)
        self.assertEqual(r['task_issue_detection']['precision'],0.5)
        self.assertEqual(r['task_issue_detection']['recall'],0.5)
    def test_gold_documents_and_sections_exist(self):
        gold=prepare.read(prepare.HERE/'gold_review.json');suite=prepare.read(prepare.HERE/'tasks.json')
        self.assertEqual(len(gold),24);self.assertEqual(len(suite['tasks']),24)
        for task in suite['tasks']:
            self.assertEqual(set(task['personas']),set(prepare.PERSONAS))
            g=gold[task['id']];texts='\n'.join((prepare.HERE/'materials'/name).read_text() for name in g['document_ids'])
            for section in g['section_ids']:self.assertIn('['+section+']',texts)
if __name__=='__main__':unittest.main()
