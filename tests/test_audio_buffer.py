"""Exercise capture/connection ordering without a microphone or ASR server."""
import asyncio
import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from audio import Session


class Process:
    def __init__(self):
        self.stdout=asyncio.StreamReader(limit=512*1024);self.stderr=asyncio.StreamReader()
        self.stdin=self;self.returncode=None;self.sent=[];self.done=asyncio.Event()

    def emit(self,event):
        self.stdout.feed_data((json.dumps(event)+'\n').encode())

    def write(self,data):
        event=json.loads(data);self.sent.append(event)
        if event['type']=='finish':
            self.emit({'type':'final_timestamps','text':'早开口','utterance_final':False})
            self.emit({'type':'final','text':'早开口','utterance_final':True})
            self.emit({'type':'closed'});self.close(0)

    async def drain(self): pass

    def close(self,code):
        if self.returncode is None:
            self.returncode=code;self.stdout.feed_eof();self.stderr.feed_eof();self.done.set()

    def terminate(self): self.close(-15)
    def kill(self): self.close(-9)
    async def wait(self):
        await self.done.wait();return self.returncode


class BufferedAudio(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.provider=Process();self.capture=Process();self.recording=asyncio.Event()
        self.pcm=b'\x01\x02'*1600
        self.capture.stdout.feed_data(self.pcm)
        self.session=Session(lambda kind,payload: self.recording.set() if kind=='recording' else None)

    async def spawn(self,*command,**kwargs):
        return self.capture if command[0]=='parec' else self.provider

    async def test_release_before_connection_preserves_initial_audio(self):
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            task=asyncio.create_task(self.session.run())
            await asyncio.wait_for(self.recording.wait(),2)
            await asyncio.sleep(.06)
            self.session.stop.set()
            await asyncio.sleep(.12)
            self.assertIsNotNone(self.capture.returncode)
            self.assertEqual(self.provider.sent,[])
            self.provider.emit({'type':'session_started'})
            outcome=await asyncio.wait_for(task,2)
        self.assertEqual(outcome['text'],'早开口')
        self.assertEqual(outcome['audio_seconds'],.1)
        self.assertEqual(outcome['peak'],513)
        self.assertEqual([e['type'] for e in self.provider.sent],['audio','finish'])
        self.assertEqual(base64.b64decode(self.provider.sent[0]['audio_base64']),self.pcm)

    async def test_cancel_discards_untransmitted_buffer(self):
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            task=asyncio.create_task(self.session.run())
            await asyncio.wait_for(self.recording.wait(),2)
            self.session.cancel.set()
            outcome=await asyncio.wait_for(task,2)
        self.assertIsNone(outcome['text']);self.assertEqual(self.provider.sent,[])
        self.assertIsNotNone(self.provider.returncode);self.assertIsNotNone(self.capture.returncode)

    async def test_connection_buffer_is_bounded(self):
        self.capture.stdout.feed_data(b'\0'*640001)
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            outcome=await asyncio.wait_for(self.session.run(),2)
        self.assertIsNone(outcome['text']);self.assertTrue(outcome['error'])
        self.assertEqual(self.provider.sent,[])
        self.assertIsNotNone(self.capture.returncode)

    async def test_capture_failure_reaps_provider(self):
        async def fail(*command,**kwargs):
            if command[0]=='parec': raise FileNotFoundError('capture unavailable')
            return self.provider
        with patch('audio.asyncio.create_subprocess_exec',side_effect=fail):
            with self.assertRaises(FileNotFoundError): await self.session.run()
        self.assertIsNotNone(self.provider.returncode)

    async def test_provider_error_diagnostics_do_not_expose_message(self):
        self.provider.emit({'type':'error','message':'Connection timed out token=private-secret'})
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            outcome=await asyncio.wait_for(self.session.run(),2)
        self.assertEqual(outcome['error_category'],'timeout')
        self.assertEqual(outcome['provider_events'],['error'])
        self.assertNotIn('private-secret',json.dumps(outcome))

    async def test_streaming_revisions_preview_without_promoting_partial_to_final(self):
        events=[]
        self.session.callback=lambda kind,payload: events.append((kind,payload))
        for text in ('初步','初步','修订','', '下一句','错误\n','x'*65537):
            self.provider.emit({'type':'partial','text':text})
        self.provider.emit({'type':'closed'})
        self.provider.close(0)
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            outcome=await self.session.run()
        self.assertEqual([p['text'] for k,p in events if k=='preview'],['初步','修订','','下一句'])
        self.assertIsNone(outcome['text'])

    async def test_cancellation_suppresses_queued_preview(self):
        events=[]
        self.session.callback=lambda kind,payload: events.append((kind,payload))
        self.session.cancel.set()
        self.provider.emit({'type':'partial','text':'过期'})
        with patch('audio.asyncio.create_subprocess_exec',side_effect=self.spawn):
            await self.session.run()
        self.assertFalse(any(k=='preview' for k,p in events))


if __name__=='__main__': unittest.main()
