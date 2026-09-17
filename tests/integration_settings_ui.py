"""Open and close only this checkout's private official settings window."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from runtime import ROOT, STATE, KEYBOARD_PREFIX, SETTINGS_PREFIX, config_path, wine, wine_env
if os.environ.get('DOUBAO_PRIVATE_DISPLAY') != '1':
    raise SystemExit('Run via scripts/headless.py --prefix none')
config=config_path(KEYBOARD_PREFIX)
before=config.read_bytes()
env=dict(os.environ,DOUBAO_SETTINGS_QUIET='1')
probe_env=wine_env(SETTINGS_PREFIX,True)
with (STATE/'settings-ui-test.log').open('w') as log:
    ui=subprocess.Popen([sys.executable,str(ROOT/'bridge/settings.py')],env=env,stdout=log,stderr=log)
    try:
        deadline=time.monotonic()+60
        found=False
        while time.monotonic()<deadline:
            if ui.poll() is not None:raise RuntimeError('Settings exited before opening; see settings-ui-test.log')
            with (STATE/'settings-window-text.log').open('w+') as probe_log:
                result=subprocess.run([wine(),str(ROOT/'build/settings-ui-probe.exe')],env=probe_env,
                                      stdout=probe_log,stderr=log,text=True,timeout=45)
                probe_log.seek(0);window_text=probe_log.read()
            if '豆包输入法设置' in window_text:
                found=True;break
            time.sleep(1)
        if not found:raise RuntimeError('Settings window not found')
        time.sleep(2)
        try:
            from PIL import ImageGrab
            ImageGrab.grab(xdisplay=env['DISPLAY']).save(STATE/'settings-preview.png')
        except ImportError:pass
        subprocess.run([wine(),str(ROOT/'build/settings-ui-probe.exe'),'--close'],env=probe_env,
                       stdout=log,stderr=log,check=True,timeout=15)
        if ui.wait(timeout=30):raise RuntimeError('Settings wrapper exited unsuccessfully')
        if config.read_bytes()!=before:raise RuntimeError('Opening and closing changed keyboard config')
        (STATE/'settings-ui.json').write_text(json.dumps({'passed':True,
            'official_window_found':True,'clean_close':True,'keyboard_config_unchanged':True},indent=2)+'\n')
        print('PASS official settings opens and closes without changing live configuration')
    finally:
        if ui.poll() is None:
            # Terminate the wrapper's own prefix, never a user's other Wine session.
            from runtime import wineserver
            subprocess.run([wineserver(),'-k'],env=probe_env,stdout=log,stderr=log,timeout=10)
            ui.terminate()
            try:ui.wait(timeout=10)
            except subprocess.TimeoutExpired:ui.kill();ui.wait()
