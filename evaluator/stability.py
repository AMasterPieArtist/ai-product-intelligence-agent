"""Bounded recovery for navigation only, before a question can be submitted."""
import asyncio

TRANSIENT_NAVIGATION_ERRORS = (
    'net::ERR_CONNECTION_CLOSED', 'net::ERR_CONNECTION_RESET',
    'net::ERR_TIMED_OUT', 'net::ERR_CONNECTION_TIMED_OUT',
    'net::ERR_NETWORK_CHANGED', 'net::ERR_ABORTED',
)

async def open_page(page, url, events, save, attempts=3, reload=False):
    for attempt in range(1, attempts + 1):
        entry = {'attempt': attempt, 'phase': 'before_question', 'status': 'started'}
        events.append(entry)
        save()
        try:
            if reload:
                await page.reload(wait_until='domcontentloaded', timeout=30000)
            else:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except Exception as exc:
            entry.update(status='error', error=f'{type(exc).__name__}: {exc}')
            save()
            transient = (any(code in str(exc) for code in TRANSIENT_NAVIGATION_ERRORS)
                         or type(exc).__name__ == 'TimeoutError')
            if not transient or attempt == attempts or page.is_closed():
                raise
            # This helper is called before an adapter or question exists.
            await asyncio.sleep(attempt * 2)
        else:
            entry['status'] = 'finished'
            save()
            return

def batch_outcome(records, planned):
    succeeded = sum(r['agent_status'] == 'finished' for r in records)
    errors = len(records) - succeeded
    if len(records) == planned:
        status = 'finished' if not errors else 'completed_with_errors'
    else:
        status = 'stopped_with_errors'
    return dict(status=status, attempted_runs=len(records),
                successful_runs=succeeded, failed_runs=errors)
