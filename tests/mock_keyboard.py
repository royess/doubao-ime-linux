"""Deterministic socket fixture for Fcitx integration, not a Doubao engine."""
import json
import os
from pathlib import Path
import signal
import socket

path = Path(os.environ['DOUBAO_KEYBOARD_SOCKET'])
composition = ''
running = True


def stop(*args):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(str(path))
os.chmod(path, 0o600)
server.listen(4)
server.settimeout(0.2)
try:
    while running:
        try: client, _ = server.accept()
        except socket.timeout: continue
        with client:
            client.settimeout(2)
            command = bytearray()
            while b'\n' not in command:
                chunk = client.recv(256)
                if not chunk: break
                command.extend(chunk)
                if len(command) > 256: raise ValueError('Oversized test request')
            parts = command.decode('ascii').split()
            result, commit = 0, ''
            if parts[:1] in (['F'], ['R']): composition = ''
            elif parts[:1] == ['S'] and composition == 'nihao':
                commit = ['你好', '您好'][int(parts[1])]
                composition, result = '', 3
            elif parts[:1] == ['K'] and parts[2] == '0':
                key = int(parts[1])
                if 65 <= key <= 90:
                    composition += chr(key).lower()
                    result = 1
                elif key == 8:
                    composition, result = composition[:-1], 1
                elif key == 27:
                    composition, result = '', 1
            preedit = "ni'hao" if composition == 'nihao' else composition
            reply = {'result': result, 'preedit': preedit, 'cursor': len(preedit),
                     'selected': 0, 'candidates': '你好\n您好' if composition == 'nihao' else '',
                     'commit': commit}
            client.sendall((json.dumps(reply, ensure_ascii=False) + '\n').encode())
finally:
    server.close()
    path.unlink(missing_ok=True)
