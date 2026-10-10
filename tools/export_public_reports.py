"""Rebuild public report snapshots from the reviewed index, without API calls."""
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'benchmarks'))
from campaign_report import write_reports


def export():
    index = ROOT / 'docs/evidence/expanded_reviews.json'
    data = json.loads(index.read_text(encoding='utf-8'))
    public = copy.deepcopy(data)
    for row in public['rows']:
        for cell in row['products'].values():
            cell['report_path'] = '../evidence/expanded_reviews.json'
    target = ROOT / 'docs/reports'
    target.mkdir(parents=True, exist_ok=True)
    mapping = {'campaign_matrix.html': 'comparison_matrix.html',
               'campaign_matrix.md': 'comparison_matrix.md',
               'scenario_recommendations.html': 'scenario_recommendations.html',
               'scenario_recommendations.md': 'scenario_recommendations.md'}
    navigation = ('<nav aria-label="成果导航" style="padding:14px 24px;background:#fff;border-bottom:1px solid #dce3ed;display:flex;gap:20px;flex-wrap:wrap;font:14px system-ui">'
                  '<a href="../index.html">成果首页</a><a href="scenario_recommendations.html">场景建议</a>'
                  '<a href="comparison_matrix.html">对比矩阵</a><a href="../evidence/expanded_reviews.json">公开复核索引</a></nav>')
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        write_reports(folder, public)
        for source, dest in mapping.items():
            text = (folder / source).read_text(encoding='utf-8')
            text = text.replace('原始对话报告', '公开复核索引')
            text = text.replace('原始对话链接需与原项目results目录一起保存。',
                                '链接指向公开复核索引；历史原始路径仅供定位，全量截图与日志未随公开包分发。')
            if dest.endswith('.html'):
                text = text.replace('<main>', navigation + '<main>', 1)
            else:
                text += '\n\n[成果导航页](../index.html) · [公开复核索引](../evidence/expanded_reviews.json)\n'
            (target / dest).write_text(text, encoding='utf-8')
    return list(mapping.values())


if __name__ == '__main__':
    for name in export():
        print('Updated: docs/reports/' + name)
