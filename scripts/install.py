#!/usr/bin/env python3
"""Install only reviewed files. Never enable services or change input methods."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import shlex
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from runtime import ROOT, STATE


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unit_quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def plan(prefix, unit_dir, voice=False, settings=False):
    for value in (ROOT, STATE, prefix, unit_dir):
        if any(c in str(value) for c in '\n\r\x00'):
            raise ValueError('Installation paths must not contain control characters')
    files = {}
    def put(path, data, mode=0o644):
        files[path] = (data.encode() if isinstance(data, str) else data, mode)
    def launcher(name, arguments):
        path = prefix / 'bin' / name
        put(path, '#!/bin/sh\nexport DOUBAO_STATE_DIR='+shlex.quote(str(STATE))+'\nexec '+
            shlex.join([sys.executable, *map(str, arguments)])+' "$@"\n', 0o755)
        return path
    for addon in ['doubaoime'] + (['doubaovoice'] if voice else []):
        library = prefix / 'lib/fcitx5' / (addon + '.so')
        put(library, (ROOT / 'build/fcitx' / (addon + '.so')).read_bytes())
        put(prefix / 'share/fcitx5/addon' / (addon + '.conf'),
            (ROOT / 'fcitx5' / (addon + '.conf')).read_text().replace(
                'Library='+addon, 'Library='+str(library.with_suffix(''))))
    put(prefix / 'share/fcitx5/inputmethod/doubao.conf', (ROOT/'fcitx5/doubao.conf').read_bytes())
    commands = {'keyboard': launcher('doubao-keyboard', [ROOT/'scripts/headless.py',
                    '--prefix', 'keyboard', '--', sys.executable, ROOT/'bridge/keyboard_broker.py'])}
    if voice: commands['voice'] = launcher('doubao-voice-daemon', [ROOT/'bridge/daemon.py'])
    if voice: launcher('doubao-voice', [ROOT/'bridge/control.py'])
    for kind, command in commands.items():
        put(unit_dir / f'doubao-{kind}.service', f'''[Unit]
Description=Doubao {kind} for Fcitx 5
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart={unit_quote(command)}
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
KillMode=mixed
UMask=0077

[Install]
WantedBy=graphical-session.target
''')
    if settings:
        command = launcher('doubao-settings', [ROOT/'bridge/settings.py'])
        desktop_command = str(command).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
        put(prefix/'share/applications/doubao-settings.desktop', f'''[Desktop Entry]
Type=Application
Name=Doubao input settings
Name[zh_CN]=豆包输入法设置（官方）
Comment=Keyboard settings for the experimental Fcitx bridge
Exec="{desktop_command}"
Icon=input-keyboard
Terminal=false
Categories=Settings;
''')
    return files


def atomic(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.doubao-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def apply(files, manifest):
    if manifest.exists(): raise RuntimeError('Already installed; uninstall first using the existing manifest')
    conflicts = [str(path) for path in files if path.exists() or path.is_symlink()]
    if conflicts: raise RuntimeError('Existing files will not be replaced: ' + ', '.join(conflicts))
    written = []
    try:
        for path, (data, mode) in files.items():
            # O_EXCL reserves the target against an intervening creator.
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
            os.close(fd); written.append(path)
            atomic(path, data, mode)
        payload = {'root': str(ROOT), 'files': {str(p): digest(d) for p, (d, _) in files.items()}}
        atomic(manifest, (json.dumps(payload, indent=2)+'\n').encode(), 0o600)
    except BaseException:
        for path in reversed(written): path.unlink(missing_ok=True)
        raise


def remove(manifest):
    record = json.loads(manifest.read_text())
    if record.get('root') != str(ROOT): raise RuntimeError('Manifest belongs to a different checkout')
    paths = [Path(name) for name in record['files']]
    for path in paths:
        if path.is_symlink() or (path.exists() and digest(path.read_bytes()) != record['files'][str(path)]):
            raise RuntimeError('Installed file modified; retained all files: ' + str(path))
    for path in paths: path.unlink(missing_ok=True)
    manifest.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'uninstall'])
    parser.add_argument('--prefix', type=Path, default=Path.home()/'.local')
    parser.add_argument('--unit-dir', type=Path, default=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'systemd/user')
    parser.add_argument('--voice', action='store_true')
    parser.add_argument('--settings', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    manifest = STATE / 'install-manifest.json'
    if args.action == 'uninstall':
        if args.dry_run: print(manifest.read_text()); return
        # Do not delete executable files underneath this installation's services.
        record = json.loads(manifest.read_text())
        for name in record['files']:
            path = Path(name)
            if path.parent == args.unit_dir.expanduser().resolve() and path.suffix == '.service':
                result = subprocess.run(['systemctl','--user','is-active','--quiet',path.name], check=False)
                if result.returncode == 0:
                    raise RuntimeError('Stop and disable this service before uninstall: ' + path.name)
        remove(manifest)
        print('Integration files removed; private runtime and settings retained.')
    else:
        if not (ROOT/'build/keyboard-host.exe').is_file(): raise RuntimeError('Build Windows helper first')
        if args.settings:
            subprocess.run([sys.executable, str(ROOT/'bridge/settings.py'), '--check'], check=True)
        files = plan(args.prefix.expanduser().resolve(), args.unit_dir.expanduser().resolve(), args.voice, args.settings)
        if args.dry_run:
            print('\n'.join(map(str, files)))
            return
        apply(files, manifest)
        print('Installed files. Enable services and add Doubao in Fcitx configuration as documented in README.md.')


if __name__ == '__main__': main()
