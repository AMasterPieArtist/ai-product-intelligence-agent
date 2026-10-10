"""Check portable code, clean notebooks, local guide links and public report counts."""
import ast
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k, v in attrs if k in ('href', 'src') and v)


def check():
    errors = []; files = [p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git', '.venv', '__pycache__', 'evaluation'))]
    code_count = 0; notebooks = 0; links = 0
    for p in files:
        name = p.relative_to(ROOT)
        if p.suffix == '.py':
            try: ast.parse(p.read_text(encoding='utf-8'), filename=str(name)); code_count += 1
            except SyntaxError as exc: errors.append(f'{name}: {exc}')
        if p.suffix == '.ipynb':
            notebooks += 1; d = json.loads(p.read_text(encoding='utf-8'))
            for i, cell in enumerate(d['cells']):
                if cell['cell_type'] != 'code': continue
                if cell.get('outputs') or cell.get('execution_count') is not None: errors.append(f'{name}: cell {i} retains outputs')
                try: ast.parse(''.join(cell['source']), filename=f'{name}#{i}')
                except SyntaxError as exc: errors.append(f'{name}: {exc}')
        if p.suffix not in ('.md', '.html'): continue
        text = p.read_text(encoding='utf-8')
        if p.suffix == '.html':
            parser = Links(); parser.feed(text); targets = parser.links
        else:
            text = re.sub(r'```.*?```', '', text, flags=re.S)
            targets = re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
        for target in targets:
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path: continue
            links += 1
            if not (p.parent / unquote(url.path)).exists(): errors.append(f'{name}: missing link {target}')
    data = json.loads((ROOT / 'docs/evidence/expanded_reviews.json').read_text(encoding='utf-8'))
    if len(data['rows']) != 96 or (data['planned'], data['completed'], data['attempts'], data['errors']) != (192, 192, 201, 9):
        errors.append('Historical public index totals changed; check provenance before publishing.')
    for pid, expected in {'dify_app': {'passed': 40, 'failed': 46, 'inconclusive': 10}, 'coze_app': {'passed': 92, 'failed': 4}}.items():
        actual = Counter(row['products'][pid]['task_completion'] for row in data['rows'])
        if dict(actual) != expected: errors.append(f'{pid}: public index task totals changed')
    html = (ROOT/'docs/reports/comparison_matrix.html').read_text(encoding='utf-8')
    if html.count('<tr data-persona=') != 96: errors.append('Matrix row count does not match public index')
    print(f'Python files: {code_count}; notebooks: {notebooks}; local links: {links}')
    if errors:
        print('\n'.join(errors)); return 1
    print('Release checks passed; historical task counts preserved.'); return 0

if __name__ == '__main__':
    raise SystemExit(check())
