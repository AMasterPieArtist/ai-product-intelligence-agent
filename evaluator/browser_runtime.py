"""Run from Notebook as a separate process. Async browser stays alive during model calls."""
import argparse
import asyncio
import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from core import normalize, clean_answer, allowed_actions

class StaleActionError(RuntimeError):
    """An action was valid when selected but no longer fits the live page."""
    def __init__(self, action, observation):
        super().__init__(f'Page state changed; action {action!r} requires a new decision')
        self.action = action
        self.observation = observation
        self.allowed = allowed_actions(observation)

class DifyBrowser:
    def __init__(self, page, out):
        self.page, self.out = page, out
        self.editor = page.get_by_placeholder('和 knowledge QA Test App 聊天', exact=True)
        self.send = page.get_by_role('button', name='发送', exact=True)
        self.questions = page.get_by_test_id('question-content')
        self.answers = page.get_by_test_id('chat-answer-container-inner')
        self.listeners = []

    async def begin(self, question, index):
        self.question, self.index = question, index
        self.q0, self.a0 = await self.questions.count(), await self.answers.count()
        if self.q0 != self.a0: raise RuntimeError('Unbalanced conversation before new turn')
        self.submitted, self.tracked = False, {}
        self.last_text, self.stable_since = '', time.monotonic()
        self.mismatch_since, self.mapping_since = None, None
        self.actual_questions = []
        def requested(req):
            if not self.submitted or req.method != 'POST': return
            try: data = req.post_data_json
            except Exception: return
            if isinstance(data, dict) and data.get('query') == question:
                self.tracked[req] = {'status': None, 'finished': False, 'failed': False}
        def response(res):
            if res.request in self.tracked: self.tracked[res.request]['status'] = res.status
        def finished(req):
            if req in self.tracked: self.tracked[req]['finished'] = True
        def failed(req):
            if req in self.tracked: self.tracked[req]['failed'] = True
        self.listeners = [('request',requested),('response',response),('requestfinished',finished),('requestfailed',failed)]
        for event, callback in self.listeners: self.page.on(event, callback)

    async def observe(self):
        input_ready = await self.editor.count()==1 and await self.editor.is_visible() and await self.editor.is_editable()
        filled = input_ready and await self.editor.input_value()==self.question
        enabled = await self.send.count()==1 and await self.send.is_visible() and await self.send.is_enabled()
        qn, an = await self.questions.count(), await self.answers.count()
        blocked = any(r['failed'] or (r['status'] is not None and r['status']>=400) for r in self.tracked.values())
        error = 'transport_failed' if blocked else None
        done = bool(self.tracked) and all(r['finished'] and not r['failed'] and r['status'] is not None and 200<=r['status']<300 for r in self.tracked.values())
        text = ''
        if self.submitted and (qn>self.q0+1 or an>self.a0+1):
            blocked, error = True, 'unexpected_extra_messages'
        if self.submitted and qn==self.q0+1:
            actual = await self.questions.nth(self.q0).inner_text()
            self.actual_questions = await self.questions.all_inner_texts()
            # Retry transient rendering, compare normalized whitespace only.
            matched = normalize(actual)==normalize(self.question)
            if not matched:
                self.mismatch_since = self.mismatch_since or time.monotonic()
                if time.monotonic()-self.mismatch_since>=10:
                    blocked, error = True, 'question_text_mismatch'
            else:
                self.mismatch_since = None
                if an==self.a0+1:
                    body = self.answers.nth(self.a0).locator(':scope > div > [data-testid="markdown-body"]')
                    if await body.count()==1 and await body.is_visible():
                        text = (await body.inner_text()).strip()
                    elif done:
                        self.mapping_since = self.mapping_since or time.monotonic()
                        if time.monotonic()-self.mapping_since>=10:
                            blocked, error = True, 'answer_dom_mapping_failed'
        if text!=self.last_text: self.last_text, self.stable_since = text, time.monotonic()
        return {'input_ready': bool(input_ready), 'question_filled': bool(filled), 'send_enabled': bool(enabled),
          'submitted': self.submitted, 'answer_ready': bool(done and text and time.monotonic()-self.stable_since>=1),
          'blocked': blocked, 'block_reason': error, 'answer_raw': text,
          'transport': list(self.tracked.values()), 'question_texts': self.actual_questions}

    async def execute(self, action):
        current = await self.observe()
        # Explicit transport/mapping blockers remain failures, not recoverable races.
        if current.get('blocked'):
            raise RuntimeError(current.get('block_reason') or 'page_blocked')
        if action not in allowed_actions(current):
            # Nothing has been clicked/filled yet; let the bounded outer loop re-observe.
            raise StaleActionError(action, current)
        if action=='fill_question': await self.editor.fill(self.question, timeout=10000)
        elif action=='click_send':
            if self.submitted or await self.editor.input_value()!=self.question: raise RuntimeError('Duplicate or incorrect submission blocked')
            self.submitted = True  # Failure stops the run; never retry an uncertain click.
            await self.send.click(timeout=10000)
        elif action=='wait': await self.page.wait_for_timeout(2500)
        return current

    async def snapshot(self, label):
        image, text = self.out/(label+'.png'), self.out/(label+'.txt')
        await self.page.screenshot(path=str(image), full_page=True, timeout=10000)
        text.write_text(await self.page.locator('body').inner_text(timeout=5000), encoding='utf-8')
        return {'screenshot': str(image), 'page_text': str(text)}

    def end(self):
        for event, callback in self.listeners: self.page.remove_listener(event, callback)
        self.listeners = []

def rule_decision(observation):
    """Choose deterministic UI actions from observed state; execution rechecks eligibility."""
    allowed = allowed_actions(observation)
    for action in ('finish', 'click_send', 'fill_question', 'wait'):
        if action in allowed:
            return {'action': action, 'reason': '依据实时页面状态执行明确动作', 'decision_mode': 'rule'}
    return {'action': 'abort', 'reason': '页面出现明确阻塞', 'decision_mode': 'rule'}

async def execute_turn(adapter, model, question, index, save, turns, max_steps=None, timeout=180):
    operation_mode = getattr(adapter, 'operation_mode', 'model')
    if operation_mode not in ('model', 'rules'):
        raise ValueError('operation_mode must be model or rules')
    snapshot_policy = getattr(adapter, 'snapshot_policy', 'transitions' if operation_mode == 'rules' else 'all')
    if snapshot_policy not in ('all','transitions'):raise ValueError('snapshot_policy must be all or transitions')
    if max_steps is None:
        max_steps = getattr(adapter, 'max_operation_steps', 80 if operation_mode == 'rules' else 12)
    if not isinstance(max_steps, int) or not 1 <= max_steps <= 200:
        raise ValueError('max_operation_steps must be 1..200')
    turn = {'turn': index, 'question': question, 'status': 'running', 'history': [], 'answer_raw': None, 'answer_clean': None}
    turns.append(turn); save()
    started = time.monotonic()
    await adapter.begin(question,index)
    try:
        for step in range(1,max_steps+1):
            if time.monotonic()-started>timeout: raise RuntimeError('turn_time_limit')
            observation = await adapter.observe()
            turn['last_observation'] = observation
            if observation.get('blocked'): raise RuntimeError(observation.get('block_reason') or 'page_blocked')
            # Do not send screenshots, local paths or nested previous usage back to the model.
            slim = {k:observation[k] for k in ('input_ready','question_filled','send_enabled','submitted','answer_ready','blocked')}
            history = [{'action':s['action'],'status':s['status']} for s in turn['history'][-4:]]
            if operation_mode == 'rules':
                d = rule_decision(observation)
            else:
                d = await asyncio.to_thread(model.decide, 'operation', {'question':question,'observation':slim,'history':history}, allowed_actions(observation))
                d['decision_mode'] = 'model'
            entry = {'step':step,'observation':slim,'allowed_actions':allowed_actions(observation),**d,'status':'started'}
            turn['history'].append(entry); save()
            try:
                actual = await adapter.execute(d['action'])
            except StaleActionError as stale:
                entry.update(status='stale', execution_observation=stale.observation,
                             execution_allowed_actions=stale.allowed)
                turn['last_observation'] = stale.observation
                save()
                print(f"Turn {index}, step {step}: {d['action']} expired; re-observing", flush=True)
                # Counts toward max_steps. Never retry a click that may have occurred.
                continue
            entry['execution_observation'] = actual
            entry['status'] = 'completed'
            previous_wait_capture = any(h.get('action')=='wait' and h.get('status')=='completed' and not h.get('artifacts',{}).get('skipped',False) for h in turn['history'][:-1])
            if snapshot_policy == 'transitions' and d['action']=='wait' and previous_wait_capture:
                entry['artifacts'] = {'skipped': True, 'reason': 'repeated_wait; final/error capture retained'}
            else:
                entry['artifacts'] = await adapter.snapshot(f'turn_{index}_step_{step:02d}')
            print(f"Turn {index}, step {step}: {d['action']} — {d['reason']}",flush=True)
            save()
            if d['action']=='abort': raise RuntimeError('agent_aborted')
            if d['action']=='finish':
                turn.update(status='finished',answer_raw=actual['answer_raw'],answer_clean=clean_answer(actual['answer_raw']))
                return turn
        raise RuntimeError('turn_step_limit')
    except Exception as e:
        turn['status']='error';turn['error']=f'{type(e).__name__}: {e}'
        if turn['history'] and turn['history'][-1]['status']=='started': turn['history'][-1]['status']='failed'
        try: turn['failure_evidence']=await adapter.snapshot(f'turn_{index}_failure')
        except Exception as capture_error: turn['capture_error']=str(capture_error)
        raise
    finally:
        adapter.end();save()

