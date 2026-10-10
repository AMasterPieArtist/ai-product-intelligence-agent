import json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from adapters import CozeBrowser
from stability import open_page
from test_coze import Page,Locator
import runner
class NavigationChecks(unittest.IsolatedAsyncioTestCase):
 async def test_transient_navigation_retry_retains_attempts(self):
  page=types.SimpleNamespace(goto=AsyncMock(side_effect=[RuntimeError('net::ERR_CONNECTION_CLOSED'),None]),is_closed=lambda:False);events=[]
  with patch('stability.asyncio.sleep',new=AsyncMock()):await open_page(page,'https://example.test',events,lambda:None)
  self.assertEqual(page.goto.await_count,2);self.assertEqual([e['status'] for e in events],['error','finished'])
 async def test_non_network_error_not_retried(self):
  page=types.SimpleNamespace(goto=AsyncMock(side_effect=RuntimeError('invalid URL')),is_closed=lambda:False)
  with self.assertRaises(RuntimeError):await open_page(page,'bad',[],lambda:None)
  self.assertEqual(page.goto.await_count,1)
 async def test_retry_is_bounded(self):
  page=types.SimpleNamespace(goto=AsyncMock(side_effect=RuntimeError('net::ERR_CONNECTION_RESET')),is_closed=lambda:False)
  with patch('stability.asyncio.sleep',new=AsyncMock()):
   with self.assertRaises(RuntimeError):await open_page(page,'https://example.test',[],lambda:None)
  self.assertEqual(page.goto.await_count,3)
class DeferredLocator(Locator):
 async def is_enabled(self):return self.page.ready and bool(self.page.value)
 async def get_attribute(self,name):return '' if name=='disabled' and not self.page.ready else None
 async def press_sequentially(self,value,**kwargs):self.page.value=value
 async def wait_for(self,**kwargs):pass
class DeferredPage(Page):
 def __init__(self,after_reload=False):
  super().__init__();self.ready=False;self.after_reload=after_reload;self.reloads=0
 def get_by_placeholder(self,*args,**kwargs):return DeferredLocator(self,'editor')
 def get_by_role(self,role,name,exact=True):return DeferredLocator(self,'send' if name=='发送' else 'stop')
 async def reload(self,**kwargs):self.reloads+=1;self.value='';self.ready=self.after_reload
class RecoveryChecks(unittest.IsolatedAsyncioTestCase):
 async def test_first_turn_reload_never_sends(self):
  page=DeferredPage(True);a=CozeBrowser(page,Path('.'));await a.begin('q',1);obs=await a.execute('fill_question')
  self.assertTrue(obs['send_enabled']);self.assertEqual(page.reloads,1);self.assertEqual(page.clicks,0);self.assertEqual(page.value,'q')
 async def test_followup_keeps_history(self):
  page=DeferredPage(True);page.q=['old q'];page.a=['old a'];a=CozeBrowser(page,Path('.'));await a.begin('followup',2)
  with self.assertRaisesRegex(RuntimeError,'disabled_after_input'):await a.execute('fill_question')
  self.assertEqual(page.reloads,0);self.assertEqual(page.q,['old q']);self.assertEqual(page.clicks,0)
 async def test_submitted_input_never_recovered(self):
  page=DeferredPage(True);a=CozeBrowser(page,Path('.'));await a.begin('q',1);a.submitted=True
  with self.assertRaisesRegex(RuntimeError,'already submitted'):await a._confirm_input()
  self.assertEqual(page.reloads,0)
 async def test_persistent_disabled_stops_after_one_reload(self):
  page=DeferredPage(False);a=CozeBrowser(page,Path('.'));await a.begin('q',1)
  with self.assertRaisesRegex(RuntimeError,'disabled_after_input'):await a.execute('fill_question')
  self.assertEqual(page.reloads,1);self.assertEqual(page.clicks,0)
class BatchChecks(unittest.IsolatedAsyncioTestCase):
 async def test_error_does_not_stop_remaining_jobs(self):
  class Manager:
   async def __aenter__(self):return object()
   async def __aexit__(self,*args):pass
  playwright=types.ModuleType('playwright');api=types.ModuleType('playwright.async_api');api.async_playwright=lambda:Manager()
  dotenv=types.ModuleType('dotenv');dotenv.load_dotenv=lambda *a,**k:None
  jobs=[('dify_app','quick_lookup',{'id':'A'}),('coze_app','quick_lookup',{'id':'B'})]
  async def fake_run(*args):
   pid,persona,task=args[4:7]
   return {'run_id':pid+'_'+task['id'],'agent_status':'error' if task['id']=='A' else 'finished'}
  with tempfile.TemporaryDirectory() as tmp:
   cfg={'suite_path':'unused','project_root':tmp,'material_manifest':[],'output_dir':str(Path(tmp)/'results'),'selected_products':['dify_app','coze_app'],'products':{p:{'material_confirmed':True} for p in ['dify_app','coze_app']},'stop_on_error':True}
   path=Path(tmp)/'config.json';path.write_text(json.dumps(cfg))
   with patch.dict('sys.modules',{'dotenv':dotenv,'playwright':playwright,'playwright.async_api':api}),patch.dict('os.environ',{'DEEPSEEK_API_KEY':'offline-test'}),patch.object(runner,'load_suite',return_value={'origin':'authored_synthetic'}),patch.object(runner,'material_manifest',return_value=[]),patch.object(runner,'plan',return_value=jobs),patch.object(runner,'matrix_report'),patch.object(runner,'init_reviews'),patch.object(runner,'run_one',new=AsyncMock(side_effect=fake_run)) as calls:
    code=await runner.run_batch(path)
   status=json.loads((Path(cfg['output_dir'])/'batch_status.json').read_text())
   self.assertEqual(calls.await_count,2);self.assertEqual(code,1);self.assertEqual(status['status'],'completed_with_errors');self.assertEqual(status['successful_runs'],1);self.assertEqual(status['failed_runs'],1)

class ModelRetryChecks(unittest.TestCase):
 def test_connection_retry_and_usage(self):
  import urllib.error
  from core import ModelClient
  response=unittest.mock.MagicMock()
  response.__enter__.return_value=response
  result={'choices':[{'message':{'content':'{"action":"finish","reason":"done"}'},'finish_reason':'stop'}],'usage':{'total_tokens':5}}
  model=ModelClient('offline','https://example.test','test')
  with patch('urllib.request.urlopen',side_effect=[urllib.error.URLError('offline'),response]),patch('core.json.load',return_value=result),patch('time.sleep'):
   decision=model.decide('persona',{},['finish'])
  self.assertEqual(decision['action'],'finish');self.assertEqual(model.calls,2);self.assertEqual(len(model.usage),1)
 def test_auth_error_not_retried(self):
  import urllib.error
  from core import ModelClient
  model=ModelClient('offline','https://example.test','test')
  error=urllib.error.HTTPError('https://example.test',401,'unauthorized',{},None)
  with patch('urllib.request.urlopen',side_effect=error) as calls:
   with self.assertRaisesRegex(RuntimeError,'HTTP 401'):model.decide('persona',{},['finish'])
  self.assertEqual(calls.call_count,1)
 def test_connection_retry_bounded(self):
  import urllib.error
  from core import ModelClient
  model=ModelClient('offline','https://example.test','test')
  with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('offline')) as calls,patch('time.sleep'):
   with self.assertRaisesRegex(RuntimeError,'3 bounded'):model.decide('persona',{},['finish'])
  self.assertEqual(calls.call_count,3)
