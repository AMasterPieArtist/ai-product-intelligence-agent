"""Page adapters: shared decision/execution loop, product-specific DOM observations.

Coze selectors were inspected on the author's deployed test application (2026-10-03).
This adapter targets that deployed application, not arbitrary Coze applications.
"""
import time
import re
from core import normalize
from browser_runtime import DifyBrowser
from stability import open_page


class CozeBrowser(DifyBrowser):
    def __init__(self, page, out):
        self.page, self.out = page, out
        self.editor = page.get_by_placeholder('输入你的问题，Enter 发送，Shift+Enter 换行…', exact=True)
        self.send = page.get_by_role('button', name='发送', exact=True)
        self.stop = page.get_by_role('button', name='停止生成', exact=True)
        # Observed message rows, excluding header/footer and welcome prompt.
        self.questions = page.locator('main main div.flex.justify-end > div')
        self.answers = page.locator('main main div.flex.justify-start > div')
        self.listeners = []
        self.input_recovery_events = []

    async def _send_diagnostics(self):
        count = await self.send.count()
        result = {'matches': count}
        if count == 1:
            result.update(
                visible=await self.send.is_visible(),
                enabled=await self.send.is_enabled(),
                disabled_attribute=await self.send.get_attribute('disabled'),
                aria_disabled=await self.send.get_attribute('aria-disabled'),
            )
        return result

    async def _wait_send_ready(self):
        # Allow deferred UI initialization/state updates, with a fixed upper bound.
        for _ in range(10):
            if (await self.editor.input_value() == self.question
                    and await self.send.count() == 1
                    and await self.send.is_visible()
                    and await self.send.is_enabled()):
                return True
            await self.page.wait_for_timeout(500)
        return False

    async def _type_question(self):
        await self.editor.fill('', timeout=10000)
        await self.editor.press_sequentially(self.question, delay=30, timeout=20000)

    async def _confirm_input(self):
        if self.submitted:
            raise RuntimeError('Coze: refuse to refill an already submitted turn')
        for attempt in range(3):
            if await self._wait_send_ready():
                return
            diagnostic = await self._send_diagnostics()
            self.input_recovery_events.append(
                {'turn': self.index, 'action': 'input_not_ready',
                 'attempt': attempt + 1, 'diagnostic': diagnostic})
            if diagnostic['matches'] != 1:
                raise RuntimeError('Coze send_button_not_unique: ' + str(diagnostic))
            if attempt < 2:
                await self._type_question()
        # Reload is safe ONLY before the first submission in an empty conversation.
        # Never reload a follow-up: it would discard its conversation history.
        if (self.index == 1 and not self.submitted and self.q0 == self.a0 == 0
                and await self.questions.count() == 0
                and await self.answers.count() == 0):
            self.input_recovery_events.append(
                {'turn': self.index, 'action': 'reload_empty_page_once'})
            navigation_events = []
            self.input_recovery_events.append(
                {'turn': self.index, 'action': 'empty_page_reload_attempts',
                 'navigation_attempts': navigation_events})
            await open_page(self.page, '', navigation_events, lambda: None, reload=True)
            await self.editor.wait_for(state='visible', timeout=15000)
            if await self.questions.count() or await self.answers.count():
                raise RuntimeError('Coze recovery_page_not_empty')
            for attempt in range(2):
                await self._type_question()
                if await self._wait_send_ready():
                    self.input_recovery_events.append(
                        {'turn': self.index, 'action': 'input_recovered_after_reload'})
                    return
        if await self.editor.input_value() != self.question:
            raise RuntimeError('Coze input_value_mismatch after bounded recovery')
        raise RuntimeError('Coze send_button_disabled_after_input: ' +
                           str(await self._send_diagnostics()))

    async def execute(self, action):
        observation = await super().execute(action)
        if action == 'fill_question':
            await self._confirm_input()
            return await self.observe()
        return observation

    async def begin(self, question, index):
        self.question, self.index = question, index
        self.q0, self.a0 = await self.questions.count(), await self.answers.count()
        if self.q0 != self.a0:
            raise RuntimeError('Unbalanced conversation before new turn')
        self.submitted = False
        self.tracked = {}
        self.last_text, self.stable_since = '', time.monotonic()
        self.mismatch_since = None
        self.actual_questions = []

    async def observe(self):
        if self.page.is_closed():
            raise RuntimeError('Coze page was closed before task completion')
        input_ready = (await self.editor.count() == 1 and await self.editor.is_visible()
                       and await self.editor.is_editable())
        filled = input_ready and await self.editor.input_value() == self.question
        enabled = (await self.send.count() == 1 and await self.send.is_visible()
                   and await self.send.is_enabled())
        busy = await self.stop.count() > 0 and await self.stop.is_visible()
        qn, an = await self.questions.count(), await self.answers.count()
        blocked, reason, text = False, None, ''
        if self.submitted and (qn > self.q0 + 1 or an > self.a0 + 1):
            blocked, reason = True, 'unexpected_extra_messages'
        if self.submitted and qn == self.q0 + 1:
            actual = await self.questions.nth(self.q0).inner_text()
            self.actual_questions = await self.questions.all_inner_texts()
            if normalize(actual) != normalize(self.question):
                self.mismatch_since = self.mismatch_since or time.monotonic()
                if time.monotonic() - self.mismatch_since >= 10:
                    blocked, reason = True, 'question_text_mismatch'
            else:
                self.mismatch_since = None
                if an == self.a0 + 1:
                    text = (await self.answers.nth(self.a0).inner_text()).strip()
        if text != self.last_text:
            self.last_text, self.stable_since = text, time.monotonic()
        # UI completion only: a stable body plus generation indicator gone.
        # This is not proof of backend success, fact accuracy or citation validity.
        ready = bool(self.submitted and text and not busy
                     and time.monotonic() - self.stable_since >= 1)
        return dict(input_ready=bool(input_ready), question_filled=bool(filled),
                    send_enabled=bool(enabled), submitted=self.submitted,
                    answer_ready=ready, blocked=blocked, block_reason=reason,
                    answer_raw=text, generation_busy=busy, transport=[],
                    question_texts=self.actual_questions)



class DifySourceBrowser(DifyBrowser):
    async def collect_source_cards(self):
        """Capture visible names in the current reply's citation area only.

        No card clicks, hidden metadata, document downloads or oracle access.
        A captured filename is not a verified source-to-excerpt mapping.
        """
        result = {
            'status': 'not_captured', 'cards': [], 'source_verified': False,
            'note': '来源区域尚未确认；不能据此判断产品没有来源。'
        }
        if await self.answers.count() != self.a0 + 1:
            return result
        captured = await self.answers.nth(self.a0).evaluate(r"""
        (element) => {
            let scope = element;
            for (let level = 0; scope && level < 4; level++) {
                const selector = '[data-testid="chat-answer-container-inner"]';
                const count = scope.querySelectorAll(selector).length
                    + (scope.matches(selector) ? 1 : 0);
                if (count !== 1 || scope.querySelector(
                    '[data-testid="question-content"]')) break;
                // The citation label must be visible and outside the answer markdown.
                const labels = [...scope.querySelectorAll('*')].filter(node =>
                    !node.closest('[data-testid="markdown-body"]') &&
                    (node.innerText || '').trim() === '引用' &&
                    node.getClientRects().length > 0);
                if (labels.length) {
                    const lines = (scope.innerText || '').split('\n')
                        .map(line => line.trim()).filter(Boolean);
                    const index = lines.lastIndexOf('引用');
                    if (index >= 0) return {
                        found: true, citation_text: lines.slice(index + 1).join('\n')
                    };
                }
                scope = scope.parentElement;
            }
            return {found: false, citation_text: ''};
        }
        """)
        if not captured.get('found'):
            return result
        names = sorted(set(re.findall(
            r'[\w\u4e00-\u9fff.-]+\.(?:pdf|txt|md|docx)\b',
            captured.get('citation_text', ''), re.I)))
        return {
            'status': 'captured' if names else 'names_not_captured',
            'cards': [{'document_name': name, 'excerpt': None,
                       'expanded': False} for name in names],
            'source_verified': False,
            'note': '仅采集可见文件名；未展开卡片，未核实文件与引文对应关系。'
        }

ADAPTERS = {'dify_app': DifySourceBrowser, 'coze_app': CozeBrowser}
COMPLETION_BASES = {
    'dify_app': 'request_finished_plus_text_stable_1s_heuristic',
    'coze_app': 'stop_button_absent_plus_text_stable_1s_heuristic',
}
