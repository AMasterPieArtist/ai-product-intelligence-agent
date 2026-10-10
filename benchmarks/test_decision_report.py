import unittest
from decision_report import decide, outcome, SCENARIOS


def row(a, b, sa='passed', sb='passed', persona='quick_lookup', tid='EV001'):
    return dict(task_id=tid, persona=persona, products={
        'dify_app':dict(execution='finished',task_completion=a,source_authenticity=sa),
        'coze_app':dict(execution='finished',task_completion=b,source_authenticity=sb)})


class DecisionTests(unittest.TestCase):
    def test_both_good_does_not_force_winner(self):
        self.assertEqual(decide([row('passed','passed')])['code'],'both')

    def test_shared_failure_blocks_whole_scenario_despite_majority(self):
        rows=[row('passed','passed') for _ in range(10)]+[row('failed','failed',tid='EV018')]
        self.assertEqual(decide(rows)['code'],'shared_gap')
        self.assertEqual(decide(rows)['shared_gap_tasks'],['EV018'])

    def test_missing_review_cannot_recommend(self):
        self.assertEqual(decide([row('not_reviewed','passed')])['code'],'pending')
        d=decide([row('passed','passed')],expected=2)
        self.assertEqual(d['code'],'pending')
        self.assertEqual(d['stats']['coze_app']['not_reviewed'],1)

    def test_source_uncertainty_is_not_false_failure(self):
        r=row('passed','passed',sa='inconclusive',persona='source_checker')
        self.assertEqual(outcome(r['products']['dify_app'],'source_checker'),'inconclusive')
        d=decide([r]);self.assertEqual(d['code'],'coze_app')
        self.assertIn('不能称为已证实失败',d['why'])

    def test_crossed_wins_not_ranked_by_total(self):
        self.assertEqual(decide([row('passed','failed'),row('failed','passed')])['code'],'unclear')

    def test_source_error_blocks_unqualified_recommendation(self):
        d=decide([row('passed','failed',sa='failed')])
        self.assertIn('先复核',d['title'])

    def test_each_task_belongs_to_exactly_one_scenario(self):
        ids=[t for s in SCENARIOS for t in s[2]]
        self.assertEqual(len(ids),24)
        self.assertEqual(set(ids),{f'EV{i:03}' for i in range(1,25)})


if __name__ == '__main__':
    unittest.main()
