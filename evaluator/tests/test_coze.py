import unittest
from pathlib import Path
from unittest.mock import patch
from adapters import CozeBrowser
from browser_runtime import StaleActionError


class Locator:
    def __init__(self, page, kind, index=None):
        self.page, self.kind, self.index = page, kind, index
    async def count(self):
        if self.kind == 'stop': return int(self.page.busy)
        if self.kind == 'send': return int(not self.page.busy)
        if self.kind in ('q','a'): return len(getattr(self.page,self.kind))
        return 1
    async def is_visible(self): return bool(await self.count())
    async def is_editable(self): return True
    async def is_enabled(self): return bool(self.page.value) and not self.page.busy
    async def input_value(self): return self.page.value
    async def get_attribute(self,name): return None
    async def fill(self,value,timeout=None): self.page.value=value
    async def click(self,timeout=None):
        self.page.clicks += 1
        self.page.q.append(self.page.value)
        self.page.a.append('正在检索知识库并思考…')
        self.page.value=''
        self.page.busy=True
    def nth(self,index): return Locator(self.page,self.kind,index)
    async def inner_text(self): return getattr(self.page,self.kind)[self.index]
    async def all_inner_texts(self): return list(getattr(self.page,self.kind))


class Page:
    def __init__(self):
        self.q=[];self.a=[];self.value='';self.busy=False;self.clicks=0
    def get_by_placeholder(self,text,exact=True):
        assert text=='输入你的问题，Enter 发送，Shift+Enter 换行…'
        return Locator(self,'editor')
    def get_by_role(self,role,name,exact=True):
        assert role=='button' and name in ('发送','停止生成')
        return Locator(self,'send' if name=='发送' else 'stop')
    def locator(self,selector):
        assert selector in ('main main div.flex.justify-end > div','main main div.flex.justify-start > div')
        return Locator(self,'q' if 'justify-end' in selector else 'a')
    def is_closed(self): return False
    async def wait_for_timeout(self,ms): pass


class CozeChecks(unittest.IsolatedAsyncioTestCase):
    async def test_busy_body_is_not_complete_and_stable_final_is_complete(self):
        p=Page();a=CozeBrowser(p,Path('.'))
        with patch('adapters.time.monotonic',return_value=100):
            await a.begin('负责人是谁？',1)
            await a.execute('fill_question')
            await a.execute('click_send')
            self.assertFalse((await a.observe())['answer_ready'])
        with patch('adapters.time.monotonic',return_value=103):
            self.assertFalse((await a.observe())['answer_ready'])
            p.a[-1]='项目负责人是林晓。来源sample_knowledge.txt'
            p.busy=False
            self.assertFalse((await a.observe())['answer_ready'])
        with patch('adapters.time.monotonic',return_value=105):
            self.assertTrue((await a.observe())['answer_ready'])
            with self.assertRaises(StaleActionError): await a.execute('click_send')
            self.assertEqual(p.clicks,1)

    async def test_followup_does_not_read_previous_answer(self):
        p=Page();p.q=['首轮问题'];p.a=['首轮回答']
        a=CozeBrowser(p,Path('.'))
        with patch('adapters.time.monotonic',return_value=100):
            await a.begin('来源是什么？',2)
            await a.execute('fill_question');await a.execute('click_send')
            p.a[-1]='第二轮回答：sample_knowledge.txt';p.busy=False
            o=await a.observe()
        self.assertEqual(o['answer_raw'],'第二轮回答：sample_knowledge.txt')
        self.assertNotIn('首轮回答',o['answer_raw'])

    async def test_extra_messages_blocked(self):
        p=Page();a=CozeBrowser(p,Path('.'))
        await a.begin('q',1);a.submitted=True
        p.q=['q','unexpected'];p.a=['a','unexpected']
        self.assertEqual((await a.observe())['block_reason'],'unexpected_extra_messages')

class ReactiveLocator(Locator):
    async def press_sequentially(self,value,**kwargs):
        self.page.value=value;self.page.synchronized=True;self.page.keys.append('type_question')
    async def is_enabled(self): return await super().is_enabled() and self.page.synchronized
    async def press(self,key):
        self.page.keys.append(key)
        if key == 'Space': self.page.value+=' '
        elif key == 'Backspace': self.page.value=self.page.value[:-1];self.page.synchronized=True
class ReactivePage(Page):
    def __init__(self): super().__init__();self.synchronized=False;self.keys=[]
    def get_by_placeholder(self,*args,**kwargs): return ReactiveLocator(self,'editor')
    def get_by_role(self,role,name,exact=True): return ReactiveLocator(self,'send' if name=='发送' else 'stop')
class InputStateChecks(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_send_recovers_without_changing_question_or_submitting(self):
        page=ReactivePage();adapter=CozeBrowser(page,Path('.'));await adapter.begin('测试问题',1)
        observation=await adapter.execute('fill_question')
        self.assertEqual(page.value,'测试问题');self.assertTrue(observation['send_enabled'])
        self.assertEqual(page.clicks,0);self.assertEqual(page.keys,['type_question'])
