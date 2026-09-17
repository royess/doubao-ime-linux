#!/usr/bin/env python3
"""Prepare pinned official components in this checkout's private state only."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from runtime import (ROOT, STATE, VERSION, VERSION_DIR, KEYBOARD_PREFIX, SETTINGS_PREFIX,
                     wine, executable)

INSTALLER_SHA = '610b8bf696835b5c4bad654b87de8695dfa808bc57aa900bcc7603e06f427f7f'
RPC_SHA = 'a3ead1a55850257bac01a878c899f42291a1f41bd2b834e0caa5c5b66a674e02'
MONO_SHA = 'df2dfc1665c2511882e7cabd56eafd0c0a3d94e5a7e86f969277f6c189d418d3'


def verify(path, expected):
    with Path(path).open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected: raise RuntimeError('Unsupported or modified input: ' + str(path))


def extract(installer):
    verify(installer, INSTALLER_SHA)
    target = STATE / 'app'
    if target.exists():
        verify(target / f'versions/v{VERSION}/rpc.dll', RPC_SHA)
        print('Official files already extracted')
        return
    with tempfile.TemporaryDirectory(prefix='extract-', dir=STATE) as tmp:
        subprocess.run([executable('innoextract', 'innoextract'), '-d', tmp, str(installer)], check=True)
        app = Path(tmp) / 'app'
        verify(app / f'versions/v{VERSION}/rpc.dll', RPC_SHA)
        shutil.move(str(app), target)
    print('Verified and extracted DoubaoIME ' + VERSION)


def initialize(kind, mono, font):
    prefix = SETTINGS_PREFIX if kind == 'settings' else KEYBOARD_PREFIX
    if os.environ.get('DOUBAO_MANAGED_PREFIX') != str(prefix):
        raise RuntimeError('Initialization requires the private display/prefix wrapper')
    app = STATE / 'app'
    verify(app / f'versions/v{VERSION}/rpc.dll', RPC_SHA)
    if not (ROOT / 'build/keyboard-host.exe').is_file():
        raise RuntimeError('Run scripts/build_windows.py first')
    marker = prefix / '.doubao-release-managed'
    if prefix.exists() and not marker.exists():
        raise RuntimeError('Refusing to initialize an unowned Wine prefix')
    prefix.mkdir(parents=True, exist_ok=True)
    marker.touch(mode=0o600)
    env = dict(os.environ)
    # Suppress Mono's interactive installer; the pinned MSI is installed below.
    env['WINEDLLOVERRIDES'] = 'winemenubuilder.exe,mshtml,mscoree=d'
    subprocess.run([wine(), 'wineboot', '-u'], env=env, check=True, timeout=120)
    destination = prefix / 'drive_c/DoubaoIme'
    if not destination.exists(): shutil.copytree(app, destination)
    verify(destination / f'versions/v{VERSION}/rpc.dll', RPC_SHA)
    for hive in ('HKCU', 'HKLM'):
        subprocess.run([wine(), 'reg', 'add', hive+r'\SOFTWARE\DoubaoIme', '/v', 'VersionDir',
                        '/t', 'REG_SZ', '/d', VERSION_DIR, '/f'], check=True, timeout=45)
    # Start once to create default user configuration; never import a user's profile.
    # The engine service inherits handles. A PIPE would remain open after the
    # short-lived helper exits; use a regular file to avoid waiting for EOF.
    with (STATE / ('initialize-' + kind + '.log')).open('w+') as log:
        result = subprocess.run([wine(), str(ROOT / 'build/keyboard-host.exe')], input='Q\n',
                                text=True, stdout=log, stderr=log, timeout=60)
        log.seek(0)
        if result.returncode or '"ready":true' not in log.read():
            raise RuntimeError('Official keyboard engine failed to initialize; see initialization log')
    if kind == 'settings':
        if not mono or not font: raise RuntimeError('Settings requires --mono-msi and --font')
        verify(mono, MONO_SHA)
        subprocess.run([wine(), 'msiexec', '/i', str(mono), '/qn'], check=True, timeout=300)
        subprocess.run([wine(), 'regsvr32', '/s', 'windowscodecs.dll'], check=True, timeout=45)
        fonts = prefix / 'drive_c/windows/Fonts'
        fonts.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(font, fonts / 'NotoSansCJK-Regular.ttc')
        gac = r'C:\windows\mono\mono-2.0\lib\mono\gac'
        subprocess.run([wine(), r'C:\windows\mono\mono-2.0\lib\mono\4.5\mcs.exe',
            '-platform:x64', '-r:'+gac+r'\PresentationCore\4.0.0.0__31bf3856ad364e35\PresentationCore.dll',
            '-r:'+gac+r'\PresentationFramework\4.0.0.0__31bf3856ad364e35\PresentationFramework.dll',
            '-r:WindowsBase', '-r:System.Xaml', '-out:'+str(ROOT/'build/settings-launcher.exe'),
            str(ROOT/'bridge/settings_launcher.cs')], check=True, timeout=60)
    print('Prepared private ' + kind + ' runtime')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('extract'); p.add_argument('--installer', type=Path, required=True)
    p = sub.add_parser('init'); p.add_argument('--settings', action='store_true')
    p.add_argument('--mono-msi', type=Path); p.add_argument('--font', type=Path)
    p = sub.add_parser('_init'); p.add_argument('kind', choices=['keyboard', 'settings'])
    p.add_argument('--mono-msi', type=Path); p.add_argument('--font', type=Path)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == 'extract': extract(args.installer.expanduser().resolve())
    elif args.action == '_init': initialize(args.kind, args.mono_msi, args.font)
    else:
        kinds = ['keyboard', 'settings'] if args.settings else ['keyboard']
        for kind in kinds:
            command = [sys.executable, str(ROOT/'scripts/headless.py'), '--prefix', kind, '--',
                       sys.executable, str(Path(__file__).resolve()), '_init', kind]
            for flag, value in [('--mono-msi', args.mono_msi), ('--font', args.font)]:
                if value: command += [flag, str(value.expanduser().resolve())]
            subprocess.run(command, check=True)


if __name__ == '__main__':
    os.umask(0o077)
    main()
