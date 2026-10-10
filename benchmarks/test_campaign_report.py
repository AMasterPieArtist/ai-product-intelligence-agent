import json
import tempfile
import unittest
from pathlib import Path
import campaign_report as report


class CampaignReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.suite = dict(suite_id='fixture', tasks=[dict(id='EV001', scenario='权限', question='<script>x</script>')])

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, batch, status='finished', review=None, rid='dify_app_EV001_quick_lookup'):
        path = self.root / 'results' / batch / rid
        path.mkdir(parents=True)
        record = dict(run_id=rid, product_id='dify_app', task=dict(id='EV001'),
                      persona_id='quick_lookup', agent_status=status, turns=[{}])
        (path / 'record.json').write_text(json.dumps(record), encoding='utf-8')
        (path / 'report.md').write_text('fixture', encoding='utf-8')
        if review is not None:
            (path.parent / 'human_reviews.json').write_text(json.dumps({rid: review}), encoding='utf-8')
        return path

    def test_missing_not_reviewed_and_current_json_over_stale_matrix(self):
        self.add('一 批', review=dict(task_completion='failed', source_authenticity='inconclusive',
                                    reviewer='AI辅助', evidence_note='实际失败'))
        (self.root / 'results/一 批/matrix.md').write_text('passed')
        data = report.collect(self.root, self.suite)
        self.assertEqual(data['completed'], 1)
        self.assertEqual(data['planned'], 8)
        row = data['rows'][0]
        self.assertEqual(row['products']['dify_app']['task_completion'], 'failed')
        self.assertEqual(row['products']['coze_app']['execution'], 'not_run')
        report.write_reports(self.root, data)
        page = (self.root / 'campaign_matrix.html').read_text()
        self.assertIn('&lt;script&gt;x&lt;/script&gt;', page)
        self.assertNotIn('<script>x</script>', page)
        self.assertIn('%20', page)

    def test_failed_retry_counted_but_not_duplicate_completed(self):
        self.add('a', 'error')
        self.add('b')
        data = report.collect(self.root, self.suite)
        self.assertEqual((data['attempts'], data['errors'], data['completed']), (2, 1, 1))
        self.assertEqual(data['rows'][0]['products']['dify_app']['task_completion'], 'not_reviewed')

    def test_duplicate_semantic_combo_rejected_even_with_different_id(self):
        self.add('a')
        self.add('b', rid='different_id')
        with self.assertRaisesRegex(ValueError, '重复完成'):
            report.collect(self.root, self.suite)

    def test_invalid_review_or_missing_evidence_rejected(self):
        p = self.add('a', review=dict(task_completion='passed'))
        with self.assertRaisesRegex(ValueError, '证据'):
            report.collect(self.root, self.suite)
        (p.parent / 'human_reviews.json').write_text(json.dumps({'dify_app_EV001_quick_lookup': dict(source_authenticity='maybe')}))
        with self.assertRaisesRegex(ValueError, '无效'):
            report.collect(self.root, self.suite)

    def test_orphan_review_rejected(self):
        p = self.add('a')
        (p.parent / 'human_reviews.json').write_text(json.dumps({'missing_run': {}}))
        with self.assertRaisesRegex(ValueError, '不存在'):
            report.collect(self.root, self.suite)

    def test_cross_campaign_configuration_rejected(self):
        p = self.add('a')
        (self.root / 'campaign_manifest.json').write_text(json.dumps(dict(products={}, material_hashes={})))
        (p.parent / 'config.json').write_text(json.dumps(dict(campaign_id='wrong', products={})))
        with self.assertRaisesRegex(ValueError, '配置与campaign不一致'):
            report.collect(self.root, self.suite)


if __name__ == '__main__':
    unittest.main()
