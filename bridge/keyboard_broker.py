#!/usr/bin/env python3
"""Local, same-user socket for a single official Doubao keyboard engine."""
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import struct
import subprocess

from runtime import ROOT, STATE, KEYBOARD_PREFIX, wine, keyboard_socket
WINE=wine()
if os.getenv('WINEPREFIX')!=str(KEYBOARD_PREFIX):
    raise SystemExit('Use scripts/headless.py --prefix keyboard')
sock_path=keyboard_socket()
os.umask(0o077)
for hive in ('HKCU','HKLM'):
    subprocess.run([WINE,'reg','add',hive+r'\SOFTWARE\DoubaoIme','/v','VersionDir','/t','REG_SZ',
                    '/d',r'C:\DoubaoIme\versions\v0.9.0.0','/f'],check=True,timeout=45,stdout=subprocess.DEVNULL)
log=(STATE/'keyboard-host.log').open('a')
host=subprocess.Popen([WINE,str(ROOT/'build/keyboard-host.exe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
selector=selectors.DefaultSelector();selector.register(host.stdout,selectors.EVENT_READ)
pending=bytearray()

def response(timeout=1):
    import time
    deadline=time.monotonic()+timeout
    while b'\n' not in pending:
        remaining=deadline-time.monotonic()
        if remaining<=0 or not selector.select(remaining):raise TimeoutError('Keyboard engine timed out')
        chunk=os.read(host.stdout.fileno(),4096)
        if not chunk:raise RuntimeError('Keyboard engine exited')
        pending.extend(chunk)
        if len(pending)>1000000:raise ValueError('Oversized response')
    line,_,rest=pending.partition(b'\n');pending[:]=rest
    return json.loads(line)

def transact(command):
    host.stdin.write((command+'\n').encode());host.stdin.flush()
    return response()

server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
running=True
def stop(*args):
    global running
    running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
bound=False
try:
    if not response(30).get('ready'):raise RuntimeError('Keyboard not ready')
    if sock_path.exists():
        probe=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:probe.connect(str(sock_path))
        except ConnectionRefusedError:sock_path.unlink()
        else:raise RuntimeError('Keyboard socket already owned by another service')
        finally:probe.close()
    server.bind(str(sock_path));bound=True;os.chmod(sock_path,0o600)
    server.listen(4);server.settimeout(0.5)
    print('Doubao keyboard ready',flush=True)
    while running:
        try:client,_=server.accept()
        except socket.timeout:continue
        with client:
            _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid!=os.getuid():continue
            client.settimeout(1)
            command=bytearray()
            try:
                while b'\n' not in command and len(command)<256:
                    chunk=client.recv(256)
                    if not chunk:break
                    command.extend(chunk)
                text=command.decode('ascii').strip()
            except (UnicodeDecodeError,TimeoutError,ConnectionError):
                continue
            import re
            if not re.fullmatch(r'(F|R|K (?:[0-9]{1,5}) [01]|S (?:[0-9]{1,2}))',text):continue
            payload=transact(text)
            try:client.sendall((json.dumps(payload,ensure_ascii=False)+'\n').encode())
            except (BrokenPipeError,ConnectionResetError):
                # A timed-out frontend must never receive a stale commit later.
                transact('R')
finally:
    server.close()
    if bound:sock_path.unlink(missing_ok=True)
    if host.poll() is None:host.terminate()
    try:host.wait(timeout=3)
    except subprocess.TimeoutExpired:host.kill();host.wait()
    log.close()
