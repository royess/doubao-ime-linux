"""Real official-engine checks, using only settings-prefix; restore its config."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from runtime import ROOT, STATE, SETTINGS_PREFIX, wine, wineserver, config_path
PREFIX=SETTINGS_PREFIX
WINE=wine()
assert os.environ.get('DOUBAO_MANAGED_PREFIX') == str(PREFIX)
CONFIG=config_path(PREFIX)
original = CONFIG.read_bytes()
rows = []
log = (STATE / 'settings-engine.log').open('w')

def scenario(name, patch, text, expected=None):
    config = json.loads(original)
    config['keyboard'].update(patch)
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    host = subprocess.Popen([WINE, str(ROOT / 'build/keyboard-host.exe')], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=log)
    selector = selectors.DefaultSelector()
    selector.register(host.stdout, selectors.EVENT_READ)
    pending = bytearray()

    def reply(timeout=40):
        deadline = time.monotonic() + timeout
        while b'\n' not in pending:
            if not selector.select(max(0, deadline-time.monotonic())):
                raise TimeoutError('engine response')
            data = os.read(host.stdout.fileno(), 65536)
            if not data: raise RuntimeError('engine exited')
            pending.extend(data)
        line, _, rest = pending.partition(b'\n'); pending[:] = rest
        return json.loads(line)

    def call(cmd):
        host.stdin.write((cmd+'\n').encode()); host.stdin.flush()
        return reply()

    try:
        assert reply().get('ready')
        call('F')
        for c in text:
            result = call(f'K {ord(c.upper())} 0')
            call(f'K {ord(c.upper())} 1')
        row = dict(test=name, patch=patch, text=text, preedit=result['preedit'],
                   candidates=result['candidates'].splitlines()[:20])
        if expected is not None: row['passed'] = row['candidates'][0] == expected
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        host.terminate()
        host.wait(timeout=10)
        subprocess.run([wineserver(), '-k'],
                       stdout=log, stderr=log, timeout=15)
        subprocess.run([wineserver(), '-w'],
                       stdout=log, stderr=log, timeout=15)
        selector.close()

try:
    scenario('pinyin baseline', {'keyboardType_v3':'pinyin','defaultTraditional':False}, 'hanyu', '汉语')
    scenario('traditional', {'keyboardType_v3':'pinyin','defaultTraditional':True}, 'hanyu', '漢語')
    scenario('xiaohe double pinyin', {'keyboardType_v3':'shuangpin','shuangpinScheme_v3':'xiaohe','defaultTraditional':False}, 'nihc', '你好')
    scenario('ziranma double pinyin', {'keyboardType_v3':'shuangpin','shuangpinScheme_v3':'ziranma','defaultTraditional':False}, 'nihk', '你好')
    scenario('wubi 86', {'keyboardType_v3':'wubi','wubiScheme':'86'}, 'wqi', '你')
    scenario('emoji disabled', {'keyboardType_v3':'pinyin','enableEmoji':False}, 'nihao')
finally:
    CONFIG.write_bytes(original)
    log.close()
    (STATE/'settings-engine.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
assert len([r for r in rows if r.get('passed')]) == 5, 'Required engine settings check failed'
