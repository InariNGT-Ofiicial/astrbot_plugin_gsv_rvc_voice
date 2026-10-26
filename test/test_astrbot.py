"""Adapter contract tests with a stub host; never sends real messages."""
import asyncio
import importlib.util
import io
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import AsyncMock

for name in ['astrbot','astrbot.api','astrbot.api.event','astrbot.api.star','astrbot.api.message_components','astrbot.core','astrbot.core.utils','astrbot.core.utils.astrbot_path']:
    sys.modules[name] = types.ModuleType(name)
api=sys.modules['astrbot.api'];api.AstrBotConfig=dict;api.logger=types.SimpleNamespace(warning=lambda *a:None)
eventmod=sys.modules['astrbot.api.event'];eventmod.AstrMessageEvent=object
eventmod.filter=types.SimpleNamespace(command=lambda *a,**kw:lambda f:f)
star=sys.modules['astrbot.api.star'];star.Star=type('Star',(),{'__init__':lambda self,context:None});star.Context=object;star.register=lambda *a,**kw:lambda c:c
sys.modules['astrbot.api.message_components'].Record=lambda **kw:kw
sys.modules['astrbot.core.utils.astrbot_path'].get_astrbot_temp_path=tempfile.gettempdir
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'packages/astrbot_plugin_gsv_rvc_voice/main.py'
if not source.exists(): source=ROOT/'main.py'
spec=importlib.util.spec_from_file_location('adapter',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def wav():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x01\x00'*2400)
    return b.getvalue()
class Event:
    unified_msg_origin='test:session'
    def __init__(self,text):self.message_str=text
    def plain_result(self,text):return ('text',text)
    def chain_result(self,chain):return ('chain',chain)
async def collect(gen):return [x async for x in gen]

class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            m.get_astrbot_temp_path=lambda:tmp
            p=m.VoiceBridge(None,{});p.synthesize=AsyncMock(return_value=wav())
            result=await collect(p.voice(Event('/voice hello world')))
            p.synthesize.assert_awaited_once_with('hello world')
            self.assertEqual(result[0][0],'chain');self.assertTrue(Path(result[0][1][0]['file']).exists());self.assertFalse(p._busy)
    async def test_denied_long_and_blank_never_call_gateway(self):
        p=m.VoiceBridge(None,{'session_whitelist':['other']});p.synthesize=AsyncMock()
        self.assertEqual((await collect(p.voice(Event('/voice hello'))))[0][0],'text');p.synthesize.assert_not_awaited()
        p.cfg={'max_chars':3}
        for text in ['/voice','/voice hello']:
            await collect(p.voice(Event(text)))
        p.synthesize.assert_not_awaited()
    async def test_error_releases_busy_and_preserves_text_response(self):
        p=m.VoiceBridge(None,{});p.synthesize=AsyncMock(side_effect=TimeoutError())
        r=await collect(p.voice(Event('/voice 你好')));self.assertEqual(r[0][0],'text');self.assertFalse(p._busy)
    async def test_actual_http_bytes_and_reject_json(self):
        from aiohttp import web
        async def valid(request):self.assertEqual((await request.json())['input'],'你好');return web.Response(body=wav(),content_type='audio/wav')
        app=web.Application();app.router.add_post('/v1/audio/speech',valid)
        runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        try:
            port=site._server.sockets[0].getsockname()[1]
            p=m.VoiceBridge(None,{'gateway_url':f'http://127.0.0.1:{port}'})
            self.assertEqual(await p.synthesize('你好'),wav())
            with self.assertRaises(Exception):m.validate_wav(b'not a wav'*20)
        finally:await runner.cleanup()

if __name__=='__main__':unittest.main()
