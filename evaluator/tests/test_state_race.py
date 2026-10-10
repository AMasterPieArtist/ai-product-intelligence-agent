"""Exercise the actual pre-execution guard while a real model thread is pending.

No external API or real product is used. Browser observations are test fixtures.
"""
import asyncio
import threading
import unittest
from browser_runtime import DifyBrowser, StaleActionError, execute_turn


class BrowserFixture(DifyBrowser):
    def __init__(self):
        self.ready = False
        self.blocked = False
        self.executed = []
        self.submitted = True

    async def begin(self, question, index):
        self.question = question

    async def observe(self):
        return dict(input_ready=True, question_filled=False, send_enabled=False,
                    submitted=True, answer_ready=self.ready, blocked=self.blocked,
                    block_reason='transport_failed' if self.blocked else None,
                    answer_raw='项目负责人是林晓。' if self.ready else '')

    async def execute(self, action):
        result = await super().execute(action)
        self.executed.append(action)
        return result

    async def snapshot(self, label):
        return {'fixture': label}

    def end(self):
        pass


class StateRace(unittest.IsolatedAsyncioTestCase):
    async def test_answer_finishes_during_model_call(self):
        browser = BrowserFixture()
        loop = asyncio.get_running_loop()
        decision_started = asyncio.Event()
        page_changed = threading.Event()
        saved = []

        class Model:
            calls = 0
            def decide(self, task, data, allowed):
                self.calls += 1
                if self.calls == 1:
                    assert 'wait' in allowed and 'finish' not in allowed
                    loop.call_soon_threadsafe(decision_started.set)
                    if not page_changed.wait(3):
                        raise RuntimeError('fixture synchronization timeout')
                    return {'action': 'wait', 'reason': 'based on old observation'}
                assert allowed == ['finish']
                return {'action': 'finish', 'reason': 'answer now ready'}

        async def finish_response():
            await decision_started.wait()
            browser.ready = True
            page_changed.set()

        turns = []
        change_task = asyncio.create_task(finish_response())
        turn = await execute_turn(browser, Model(), '负责人是谁？', 1,
                                  lambda: saved.append(True), turns, max_steps=3)
        await change_task
        self.assertEqual(turn['status'], 'finished')
        self.assertEqual(turn['answer_clean'], '项目负责人是林晓。')
        self.assertEqual(browser.executed, ['finish'])
        first = turn['history'][0]
        self.assertEqual(first['status'], 'stale')
        self.assertFalse(first['observation']['answer_ready'])
        self.assertTrue(first['execution_observation']['answer_ready'])
        self.assertEqual(first['execution_allowed_actions'], ['finish'])

    async def test_actual_blocker_is_not_recovered(self):
        browser = BrowserFixture()
        browser.blocked = True
        with self.assertRaisesRegex(RuntimeError, 'transport_failed'):
            await browser.execute('wait')
        self.assertEqual(browser.executed, [])

    async def test_stale_click_does_not_send_again(self):
        browser = BrowserFixture()
        with self.assertRaises(StaleActionError):
            await browser.execute('click_send')
        self.assertEqual(browser.executed, [])

    async def test_repeated_state_changes_still_hit_step_limit(self):
        class Unstable(BrowserFixture):
            async def execute(self, action):
                raise StaleActionError(action, await self.observe())
        class Waiter:
            def decide(self, *args):
                return {'action': 'wait', 'reason': 'fixture'}
        turns = []
        with self.assertRaisesRegex(RuntimeError, 'turn_step_limit'):
            await execute_turn(Unstable(), Waiter(), 'q', 1, lambda: None, turns, max_steps=2)
        self.assertEqual(turns[0]['status'], 'error')
        self.assertEqual([e['status'] for e in turns[0]['history']], ['stale', 'stale'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
