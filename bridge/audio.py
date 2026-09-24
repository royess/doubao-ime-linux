"""One bounded recording session. Network and audio never run on the D-Bus loop."""
import asyncio
from array import array
import base64
from collections import deque
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]


class Result:
    def __init__(self):
        self.segment = self.final = ''
        self.closed = self.error = False

    def receive(self, event):
        kind = event.get('type')
        if kind == 'error':
            self.error = True
        elif kind == 'closed':
            self.closed = True
        elif kind in ('final', 'final_timestamps'):
            value = event.get('text')
            if not isinstance(value, str) or not value.strip() or len(value.encode()) > 65536:
                self.error = True
            elif event.get('utterance_final'):
                self.final = value
            else:
                self.segment = value

    def accepted(self, returncode, stopped, cancelled):
        # Upstream can label a partial result final on shutdown. Require a real
        # segment final as well as its matching end-of-utterance acknowledgement.
        if returncode == 0 and stopped and not cancelled and self.closed and not self.error:
            if self.segment and self.final == self.segment:
                return self.final
        return None


class Session:
    def __init__(self, callback, source=None):
        self.callback, self.source = callback, source
        self.stop = threading.Event()
        self.cancel = threading.Event()

    def start(self):
        threading.Thread(target=self._thread, daemon=True).start()

    def _thread(self):
        try:
            outcome = asyncio.run(self.run())
        except Exception as error:
            outcome = {'error': type(error).__name__, 'text': None}
        self.callback('done', outcome)

    async def run(self):
        provider = await asyncio.create_subprocess_exec(sys.executable, str(ROOT/'scripts/provider.py'),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        capture = None
        feed_task = None
        ready = asyncio.Event()
        result = Result()
        diagnostics = []
        queued = deque()
        queued_bytes = 0
        captured_bytes = 0
        peak = 0
        provider_events = []
        error_category = None

        def classify(message):
            message = str(message).lower()
            for category, words in (
                ('timeout', ('timeout', 'timed out')),
                ('connection', ('connection', 'websocket', 'handshake')),
                ('authentication', ('unauthorized', 'forbidden', 'credential', 'token')),
                ('no-speech', ('no speech', 'empty audio', 'no valid audio')),
            ):
                if any(word in message for word in words):
                    return category
            return 'upstream-error'

        async def output():
            nonlocal error_category
            async for line in provider.stdout:
                event = json.loads(line)
                kind = event.get('type')
                if kind in ('session_started', 'final', 'final_timestamps', 'closed', 'error'):
                    if len(provider_events) < 32:
                        provider_events.append(kind)
                if kind == 'error':
                    error_category = classify(event.get('message', ''))
                result.receive(event)
                if event.get('type') == 'session_started':
                    ready.set()

        async def errors():
            nonlocal error_category
            async for line in provider.stderr:
                # Do not relay upstream errors containing credentials or URLs.
                diagnostics.append(True)
                if not error_category:
                    error_category = classify(line.decode(errors='replace'))

        async def send(event):
            provider.stdin.write((json.dumps(event)+'\n').encode())
            await asyncio.wait_for(provider.stdin.drain(), 2)

        async def feed():
            nonlocal queued_bytes, captured_bytes, peak
            while not self.stop.is_set() and not self.cancel.is_set():
                chunk = await capture.stdout.read(3200)
                if not chunk:
                    break
                if self.stop.is_set() or self.cancel.is_set():
                    break
                queued.append(chunk)
                queued_bytes += len(chunk)
                captured_bytes += len(chunk)
                samples = array('h', chunk[:len(chunk)//2*2])
                peak = max(peak, max(map(abs, samples), default=0))
                # At most 20 seconds of 16 kHz mono PCM while connecting.
                if queued_bytes > 640000:
                    result.error = True
                    return

        async def terminate(process):
            if process and process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

        readers = [asyncio.create_task(output()), asyncio.create_task(errors())]
        finished = False
        try:
            command = ['parec', '--raw', '--format=s16le', '--rate=16000', '--channels=1',
                       '--latency-msec=20', '--client-name=Doubao-Fcitx-Voice']
            if self.source:
                command += ['--device='+self.source]
            if not self.cancel.is_set() and not self.stop.is_set():
                capture = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                              stderr=asyncio.subprocess.DEVNULL)
                feed_task = asyncio.create_task(feed())
                self.callback('recording', {})
            while provider.returncode is None:
                if self.cancel.is_set() or result.error:
                    break
                if self.stop.is_set() and capture and capture.returncode is None:
                    await terminate(capture)
                    if feed_task:
                        await feed_task
                if ready.is_set() and not finished:
                    while queued and not self.cancel.is_set():
                        chunk = queued.popleft(); queued_bytes -= len(chunk)
                        await send({'type': 'audio', 'audio_base64': base64.b64encode(chunk).decode()})
                    if self.stop.is_set() and not self.cancel.is_set():
                        await send({'type': 'finish'})
                        finished = True
                if capture and capture.returncode is not None and not self.stop.is_set():
                    result.error = True
                    break
                if feed_task and feed_task.done() and not self.stop.is_set():
                    result.error = True
                    break
                await asyncio.sleep(0.05)
            if provider.returncode is None:
                await terminate(provider)
            await asyncio.gather(*readers)
            return {'text': result.accepted(provider.returncode, finished, self.cancel.is_set()),
                    'error': 'provider-or-capture-error' if result.error or provider.returncode else None,
                    'provider_exit': provider.returncode, 'diagnostic_count': len(diagnostics),
                    'audio_seconds': round(captured_bytes / 32000, 2), 'peak': peak,
                    'provider_events': provider_events, 'error_category': error_category}
        finally:
            await terminate(capture)
            await terminate(provider)
            if feed_task:
                feed_task.cancel()
                await asyncio.gather(feed_task, return_exceptions=True)
            for task in readers:
                task.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
