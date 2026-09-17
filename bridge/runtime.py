"""Project-local runtime configuration; no desktop changes on import."""
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config.local.json'
OPTIONS = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
STATE = Path(os.environ.get('DOUBAO_STATE_DIR', OPTIONS.get('state_dir', ROOT / 'work'))).expanduser().resolve()
VERSION = '0.9.0.0'
VERSION_DIR = rf'C:\DoubaoIme\versions\v{VERSION}'
KEYBOARD_PREFIX = STATE / 'wineprefix'
SETTINGS_PREFIX = STATE / 'settings-prefix'


def executable(key, default):
    value = os.environ.get('DOUBAO_' + key.upper(), OPTIONS.get(key, default))
    found = shutil.which(str(value))
    if not found:
        raise RuntimeError(f'Missing executable {value!r}; set {key} in config.local.json')
    return str(Path(found).absolute())


def wine():
    return executable('wine', 'wine')


def wineserver():
    sibling = Path(wine()).with_name('wineserver')
    return executable('wineserver', str(sibling) if sibling.exists() else 'wineserver')


def config_path(prefix):
    users = prefix / 'drive_c/users'
    candidates = sorted(p for p in users.iterdir()
                        if p.is_dir() and p.name.lower() not in ('public', 'default', 'all users'))
    requested = OPTIONS.get('wine_user')
    if requested:
        if requested in ('.', '..') or '/' in requested or '\\' in requested:
            raise ValueError('wine_user must be a single directory name')
        candidates = [users / requested]
    if len(candidates) != 1:
        raise RuntimeError('Cannot identify Wine user; set wine_user in config.local.json')
    return candidates[0] / 'AppData/Roaming/DoubaoIme/conf/config.json'


def keyboard_socket():
    return Path(os.environ.get('DOUBAO_KEYBOARD_SOCKET',
                str(Path(os.environ['XDG_RUNTIME_DIR']) / 'doubaoime-keyboard.sock')))


def wine_env(prefix, settings=False):
    return dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all',
                DOUBAO_MANAGED_PREFIX=str(prefix), windir=r'C:\windows',
                WINEDLLOVERRIDES=('winemenubuilder.exe,mshtml=d;mscoree=b' if settings
                                 else 'winemenubuilder.exe,mscoree,mshtml=d'))
