"""Collect page-readiness evidence; does not send questions or grade answers."""
import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

VERSION = 'page-inspection-v3'
# Candidate editors only: this is not proof that the chat task works.
EDITOR_JS = """() => Array.from(document.querySelectorAll(
 'textarea, input[type="text"], input:not([type]), [contenteditable="true"], [role="textbox"]'
)).some(e => {
 const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
 return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
 && s.display !== 'none' && !e.disabled && !e.readOnly
 && e.getAttribute('aria-disabled') !== 'true';
})"""

def clean_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def inspect_page(args):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    run_dir = Path(args.output_root).resolve() / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    diagnostics = {k: [] for k in (
        'page_errors', 'request_failures', 'http_errors', 'console_errors',
        'api_responses', 'probe_errors')}
    pending = {}
    record = {
        'script_version': VERSION, 'run_id': args.run_id,
        'execution_status': 'running', 'task_status': 'not_evaluated',
        'readiness_status': 'not_checked', 'url': clean_url(args.url),
        'title': None, 'screenshot': None, 'page_text': None,
        'diagnostics': diagnostics, 'browser': args.browser,
        'python': sys.version.split()[0], 'platform': platform.system(),
    }
    record_path = run_dir / 'record.json'

    def save():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')

    def capture(category, detail):
        diagnostics[category].append(detail)
        print(f'[{category}] {detail}', flush=True)

    save()  # Even startup failures leave a record for this exact run.
    print(f'[{VERSION}] Run ID: {args.run_id}', flush=True)
    print(f'Record: {record_path}', flush=True)
    browser = None
    try:
        with sync_playwright() as p:
            try:
                options = {'headless': args.headless}
                if args.browser != 'chromium':
                    options['channel'] = args.browser
                browser = p.chromium.launch(**options)
                page = browser.new_page(viewport={'width': 1280, 'height': 900})

                def on_request(request):
                    if request.resource_type in ('fetch', 'xhr'):
                        pending[id(request)] = {
                            'method': request.method, 'url': clean_url(request.url),
                            'started': time.monotonic()}

                def on_response(response):
                    detail = {'status': response.status, 'url': clean_url(response.url)}
                    if response.request.resource_type in ('fetch', 'xhr'):
                        diagnostics['api_responses'].append(detail)
                    if response.status >= 400:
                        capture('http_errors', detail)

                def on_failed(request):
                    pending.pop(id(request), None)
                    capture('request_failures', {
                        'url': clean_url(request.url), 'reason': request.failure})

                page.on('request', on_request)
                page.on('requestfinished', lambda r: pending.pop(id(r), None))
                page.on('requestfailed', on_failed)
                page.on('response', on_response)
                page.on('pageerror', lambda e: capture('page_errors', str(e)))
                page.on('console', lambda m: capture('console_errors', m.text) if m.type == 'error' else None)
                print('Diagnostics enabled. Waiting for a visible editable field...', flush=True)
                try:
                    response = page.goto(args.url, wait_until='domcontentloaded', timeout=60000)
                    record['http_status'] = response.status if response else None
                    try:
                        page.wait_for_function(EDITOR_JS, timeout=args.wait_seconds * 1000)
                        record['readiness_status'] = 'editor_candidate_found'
                    except PlaywrightTimeout:
                        record['readiness_status'] = 'editor_not_found_within_timeout'
                    print('Readiness:', record['readiness_status'], flush=True)
                    if args.manual:
                        print('Manual inspection: click Resume in Inspector to save. Do not close the browser.', flush=True)
                        page.pause()
                        record['editor_after_manual'] = bool(page.evaluate(EDITOR_JS))
                except Exception as exc:
                    record['readiness_status'] = 'probe_interrupted'
                    capture('probe_errors', f'{type(exc).__name__}: {exc}')
                finally:
                    # Collect each artifact independently, including when navigation fails.
                    for name in ('title', 'page_text', 'screenshot', 'controls'):
                        try:
                            if name == 'title':
                                record['title'] = page.title()
                                record['url'] = clean_url(page.url)
                            elif name == 'page_text':
                                path = run_dir / 'page.txt'
                                path.write_text(page.locator('body').inner_text(timeout=5000), encoding='utf-8')
                                record['page_text'] = str(path)
                            elif name == 'screenshot':
                                path = run_dir / 'page.png'
                                page.screenshot(path=str(path), full_page=True, timeout=10000)
                                record['screenshot'] = str(path)
                            else:
                                record['controls'] = page.locator('input, textarea, [contenteditable], button, [role="textbox"]').evaluate_all("""els => els.map(e => ({
                                  tag: e.tagName, type: e.getAttribute('type'),
                                  role: e.getAttribute('role'), placeholder: e.getAttribute('placeholder'),
                                  label: e.getAttribute('aria-label'), disabled: !!e.disabled,
                                  visible: !!(e.getBoundingClientRect().width && e.getBoundingClientRect().height)
                                }))""")
                        except Exception as exc:
                            capture('probe_errors', f'{name}: {type(exc).__name__}: {exc}')
                    record['pending_api_requests'] = [
                        {'method': v['method'], 'url': v['url'],
                         'age_seconds': round(time.monotonic() - v['started'], 1)}
                        for v in pending.values()]
                    record['execution_status'] = (
                        'success' if record['screenshot'] and record['page_text'] and not diagnostics['probe_errors']
                        else 'partial' if record['screenshot'] or record['page_text'] else 'failed')
            finally:
                if browser:
                    browser.close()
    except Exception as exc:
        record['execution_status'] = 'failed'
        capture('probe_errors', f'{type(exc).__name__}: {exc}')
    finally:
        save()
        print('Evidence saved:', record_path, flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--run-id', default=datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    parser.add_argument('--browser', choices=['chromium', 'chrome', 'msedge'], default='chromium')
    parser.add_argument('--wait-seconds', type=int, default=30)
    parser.add_argument('--manual', action='store_true')
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in ('.', '..'):
        parser.error('run-id must be a simple directory name')
    if args.wait_seconds <= 0:
        parser.error('wait-seconds must be positive')
    # Prevent inherited debugger settings from unexpectedly pausing an automatic run.
    if not args.manual:
        os.environ.pop('PWDEBUG', None)
    inspect_page(args)
