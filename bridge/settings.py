#!/usr/bin/env python3
"""Official settings UI, isolated Wine runtime, checked merge on window close."""
import argparse
import copy
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import sys
import tempfile
import time

from runtime import ROOT, STATE, SETTINGS_PREFIX, KEYBOARD_PREFIX, config_path, wine, wineserver, keyboard_socket
PREFIX = SETTINGS_PREFIX
UNIT = 'doubao-keyboard.service'


def read_config(path):
    if path.stat().st_size > 1024*1024:
        raise ValueError('配置文件过大')
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get('keyboard'), dict):
        raise ValueError('配置文件格式不正确')
    return data


def write_config(path, data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)+'\n'
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def changed_keys(before, after):
    return {key: value for key, value in after['keyboard'].items()
            if key in before['keyboard'] and before['keyboard'][key] != value}


def merge_keyboard(before, after, current):
    changes = changed_keys(before, after)
    merged = copy.deepcopy(current)
    for key, value in changes.items():
        old = before['keyboard'][key]
        if type(value) is not type(old):
            raise ValueError('选项类型改变：'+key)
        if current['keyboard'].get(key) not in (old, value):
            raise ValueError('选项被其他程序修改，未覆盖：'+key)
        merged['keyboard'][key] = value
    return merged, changes


def notify(message):
    if os.getenv('DOUBAO_SETTINGS_QUIET') == '1': return
    if not __import__('shutil').which('notify-send'): return
    subprocess.run(['notify-send', '-a', '豆包设置', '豆包设置', message],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def wait_keyboard(timeout=30):
    path=keyboard_socket()
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(0.5)
            try:
                client.connect(str(path))
                return
            except (FileNotFoundError,ConnectionRefusedError,TimeoutError):
                pass
        time.sleep(0.2)
    raise RuntimeError('豆包键盘重启后未就绪，已尝试还原配置')


def owns_service():
    """Only this checkout's installed unit may be stopped or restarted."""
    manifest = STATE / 'install-manifest.json'
    if not manifest.is_file(): return False
    record = json.loads(manifest.read_text())
    if record.get('root') != str(ROOT): return False
    result = subprocess.run(['systemctl', '--user', 'show', UNIT, '-p', 'FragmentPath', '--value'],
                            capture_output=True, text=True, timeout=5)
    path = Path(result.stdout.strip())
    expected = record.get('files', {}).get(str(path))
    return bool(expected and path.is_file() and
                hashlib.sha256(path.read_bytes()).hexdigest() == expected)


def main():
    parser = argparse.ArgumentParser(description='打开官方豆包设置，关闭窗口后应用键盘配置')
    parser.add_argument('--check', action='store_true', help='只检查依赖，不打开窗口')
    args = parser.parse_args()
    WINE = Path(wine())
    LIVE_CONFIG = config_path(KEYBOARD_PREFIX)
    UI_CONFIG = config_path(PREFIX)
    needed = [WINE, ROOT/'build/settings-launcher.exe', ROOT/'build/keyboard-host.exe',
              PREFIX/'drive_c/windows/mono/mono-2.0/lib/mono/4.5/mscorlib.dll',
              PREFIX/'drive_c/DoubaoIme/versions/v0.9.0.0/DoubaoImeSettings.exe', LIVE_CONFIG]
    missing = [str(p) for p in needed if not p.exists()]
    if missing: raise RuntimeError('缺少设置组件：'+', '.join(missing))
    if args.check:
        print(json.dumps({'ready':True, 'live_config':str(LIVE_CONFIG),
                          'ui':'official Wine Mono WPF', 'applies':'keyboard configuration',
                          'limitations':['Windows voice shortcuts','Windows appearance/status bar',
                                         'automatic update','account/cloud sync unverified']}, ensure_ascii=False))
        return
    lock = (STATE/'settings-prefix.lock').open('a')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        notify('设置窗口已在运行。'); return
    if UI_CONFIG.resolve() == LIVE_CONFIG.resolve():
        raise RuntimeError('设置副本不能直接链接到活动配置')
    before = read_config(LIVE_CONFIG)
    seed = copy.deepcopy(before)
    seed.setdefault('app', {})['lastOpenedTab'] = 'keyboard'
    # This copy supplies the UI and cannot upgrade the pinned live engine.
    seed.setdefault('update', {})['automaticUpdateEnabled'] = False
    write_config(UI_CONFIG, seed)
    directory = STATE/'settings-backup'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    directory.mkdir(mode=0o700, parents=True)
    write_config(directory/'before.json', before)
    env = dict(os.environ, WINEPREFIX=str(PREFIX), WINEDEBUG='-all', windir=r'C:\windows',
               WINEDLLOVERRIDES='winemenubuilder.exe,mshtml=d;mscoree=b', LIBGL_ALWAYS_SOFTWARE='1')
    notify('关闭窗口后应用键盘设置。语音快捷键与候选框外观仍由 Linux 配置管理。')
    with (directory/'ui.log').open('w') as log:
        try:
            host = subprocess.Popen([str(WINE), str(ROOT/'build/keyboard-host.exe')], env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
            with selectors.DefaultSelector() as selector:
                selector.register(host.stdout, selectors.EVENT_READ)
                if not selector.select(30) or b'"ready":true' not in host.stdout.readline():
                    raise RuntimeError('官方设置后台未能启动')
            result = subprocess.run([str(WINE), str(ROOT/'build/settings-launcher.exe')], env=env,
                                    cwd=PREFIX/'drive_c/DoubaoIme/versions/v0.9.0.0', stdout=log, stderr=log)
        finally:
            subprocess.run([wineserver(), '-k'], env=env,
                           stdout=log, stderr=log, timeout=10)
            if 'host' in locals(): host.wait(timeout=10)
    after = read_config(UI_CONFIG)
    write_config(directory/'requested.json', after)
    if result.returncode:
        raise RuntimeError('设置程序异常退出，活动配置未修改；日志：'+str(directory))
    current = read_config(LIVE_CONFIG)
    merged, changes = merge_keyboard(before, after, current)
    if not changes:
        notify('没有键盘配置变更。'); return
    was_active = owns_service() and subprocess.run(['systemctl','--user','is-active','--quiet',UNIT]).returncode == 0
    if was_active:
        subprocess.run(['systemctl','--user','stop',UNIT], check=True, timeout=25)
    engine_lock = (STATE / 'wineprefix.lock').open('a')
    try: fcntl.flock(engine_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('键盘进程不是由本安装的服务管理；请先停止该进程，再应用设置')
    try:
        # Recheck after the engine has saved and stopped.
        current = read_config(LIVE_CONFIG)
        merged, changes = merge_keyboard(before, after, current)
        write_config(directory/'pre-apply.json', current)
        write_config(LIVE_CONFIG, merged)
        fcntl.flock(engine_lock, fcntl.LOCK_UN)
        if was_active:
            subprocess.run(['systemctl','--user','start',UNIT], check=True, timeout=40)
            wait_keyboard()
    except Exception:
        if was_active:
            subprocess.run(['systemctl','--user','stop',UNIT], check=True, timeout=25)
        fcntl.flock(engine_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write_config(LIVE_CONFIG, current)
        fcntl.flock(engine_lock, fcntl.LOCK_UN)
        if was_active:
            subprocess.run(['systemctl','--user','start',UNIT], timeout=40)
        raise
    finally:
        engine_lock.close()
    write_config(directory/'applied.json', merged)
    notify('已保存 '+str(len(changes))+' 项键盘设置。双拼、五笔和繁简由官方引擎处理；Windows 前端专用选项仍有限制。')


if __name__ == '__main__':
    os.umask(0o077)
    try: main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        notify('未能完成设置：'+str(error))
        raise SystemExit(1)
