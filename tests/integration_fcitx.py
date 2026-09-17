"""Real Fcitx/GTK tests on a private D-Bus session and Xvfb; no audio needed."""
import ctypes as C
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from runtime import ROOT, STATE

parser=argparse.ArgumentParser()
parser.add_argument('--mock-engine',action='store_true',help='Use a local fixture, without Wine or official components')
args=parser.parse_args()

if os.environ.get('DOUBAO_PRIVATE_DISPLAY') != '1':
    raise SystemExit('Run via scripts/headless.py on a private display')
if not args.mock_engine and not os.environ.get('DOUBAO_MANAGED_PREFIX'):
    raise SystemExit('Run via scripts/headless.py -- dbus-run-session -- python3 tests/integration_fcitx.py')
os.environ['GTK_IM_MODULE']='fcitx'
os.environ['GDK_BACKEND']='x11'
os.environ['NO_AT_BRIDGE']='1'
os.environ['GIO_USE_VFS']='local'
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gio, GLib, Gtk, Gdk
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
def dbus(path,iface,method,signature=None,args=(),connection=bus):
    return connection.call_sync('org.fcitx.Fcitx5',path,iface,method,
        GLib.Variant(signature,args) if signature else None,None,Gio.DBusCallFlags.NONE,2000,None).unpack()
if bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',
    GLib.Variant('(s)',('org.fcitx.Fcitx5',)),None,Gio.DBusCallFlags.NONE,2000,None).unpack()[0]:
    raise SystemExit('Refusing to use an existing Fcitx D-Bus session')
os.environ['GTK_IM_MODULE']='fcitx'
os.environ['GDK_BACKEND']='x11'
os.environ['NO_AT_BRIDGE']='1'
temporary=tempfile.TemporaryDirectory(prefix='fcitx-',dir=STATE)
area=Path(temporary.name)
os.environ['XDG_CONFIG_HOME']=str(area/'config')
os.environ['XDG_DATA_HOME']=str(area/'data')
os.environ['XDG_CACHE_HOME']=str(area/'cache')
os.environ['DOUBAO_KEYBOARD_SOCKET']=str(area/'keyboard.sock')
addon=area/'data/fcitx5/addon';addon.mkdir(parents=True)
for name in ['doubaoime','doubaovoice']:
    (addon/(name+'.conf')).write_text((ROOT/'fcitx5'/(name+'.conf')).read_text().replace(
        'Library='+name,'Library='+str(ROOT/'build/fcitx'/name)))
ims=area/'data/fcitx5/inputmethod';ims.mkdir(parents=True)
(ims/'doubao.conf').write_bytes((ROOT/'fcitx5/doubao.conf').read_bytes())
config=area/'config/fcitx5';config.mkdir(parents=True)
(config/'profile').write_text('[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=doubao\n\n'
    '[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName=doubao\nLayout=\n\n'
    '[GroupOrder]\n0=Default\n')
log=(STATE/'integration-fcitx.log').open('w')
broker_source=ROOT/('tests/mock_keyboard.py' if args.mock_engine else 'bridge/keyboard_broker.py')
broker=subprocess.Popen([sys.executable,str(broker_source)],stdout=log,stderr=log)
core=subprocess.Popen(['fcitx5','-D','-k','--disable','all','--enable',
    'keyboard,dbus,dbusfrontend,doubaoime,doubaovoice'],stdout=log,stderr=log)
window=Gtk.Window(title='Doubao release integration test')
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
fields=[Gtk.Entry(),Gtk.Entry(),Gtk.Entry()];fields[2].set_visibility(False)
for field in fields:box.pack_start(field,True,True,0)
window.add(box);window.show_all()
x=C.CDLL('libX11.so.6');xt=C.CDLL('libXtst.so.6')
x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_ubyte
x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
xt.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
display=x.XOpenDisplay(os.environ['DISPLAY'].encode())
if not display:raise RuntimeError('Private display unavailable')
def key(sym):
    code=x.XKeysymToKeycode(display,sym)
    xt.XTestFakeKeyEvent(display,code,1,0);xt.XTestFakeKeyEvent(display,code,0,0);x.XFlush(display)
def voice(method,*args,connection=bus):
    return dbus('/org/fcitx/Fcitx5/DoubaoDictation','org.fcitx.Fcitx5.DoubaoDictation1',
                method,'('+'s'*len(args)+')' if args else None,args,connection)[0]
results=[]
def check(name,condition):
    results.append({'test':name,'pass':bool(condition)})
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)
    if not condition:raise AssertionError(name)
def sequence():
    deadline=time.monotonic()+45
    while not (area/'keyboard.sock').exists():
        if broker.poll() is not None:raise RuntimeError('Broker exited; see work/integration-fcitx.log')
        if time.monotonic()>deadline:raise TimeoutError('Broker startup')
        yield 100
    yield 1000
    window.get_window().focus(Gdk.CURRENT_TIME);fields[0].grab_focus();yield 500
    subprocess.run(['fcitx5-remote','-s','doubao'],check=True);yield 300
    for char in 'nihao':key(ord(char));yield 150
    key(32);yield 400
    check(('fixture' if args.mock_engine else 'official')+' keyboard commits into GTK',fields[0].get_text()=='你好')
    if args.mock_engine:
        fields[0].set_text('')
        for char in 'nihao':key(ord(char));yield 100
        key(ord('2'));yield 200
        check('non-first candidate selected through Fcitx',fields[0].get_text()=='您好')
        fields[0].set_text('')
        for char in 'ni':key(ord(char));yield 100
        key(0xff1b);yield 200
        check('Escape drops uncommitted preedit',not fields[0].get_text())
        for char in 'nihao':key(ord(char));yield 100
        fields[1].grab_focus();yield 250
        check('focus loss does not commit unfinished preedit',not fields[0].get_text())
        fields[0].grab_focus();yield 200
        for char in 'nihao':key(ord(char));yield 100
        key(32);yield 200
        check('keyboard recovers after focus reset',fields[0].get_text()=='你好')
    subprocess.run(['fcitx5-remote','-s','keyboard-us'],check=True);yield 250
    token=voice('Begin');check('focused field gets ticket',bool(token))
    other=Gio.DBusConnection.new_for_address_sync(os.environ['DBUS_SESSION_BUS_ADDRESS'],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,None,None)
    check('different sender cannot consume ticket',not voice('Commit',token,'错误',connection=other))
    check('final text accepted once',voice('Commit',token,'，语音测试'))
    check('repeated final rejected',not voice('Commit',token,'重复'))
    yield 200
    check('text delivered exactly once',fields[0].get_text()=='你好，语音测试')
    token=voice('Begin');fields[1].grab_focus();yield 200
    check('focus change rejects late result',not voice('Commit',token,'错误'))
    check('new field unchanged',not fields[1].get_text())
    token=voice('Begin');key(ord('a'));yield 200
    check('typing revokes ticket',not voice('Valid',token))
    token=voice('Begin');key(0xff1b);yield 200
    check('Escape cancels ticket',not voice('Commit',token,'错误'))
    fields[2].grab_focus();yield 200
    check('password field cannot start dictation',not voice('Begin'))
    fields[0].grab_focus();yield 200
    token=voice('Begin');check('control characters rejected',not voice('Commit',token,'line\nbreak'))
    check('invalid result also consumes ticket',not voice('Valid',token))
    token=voice('Begin');check('explicit cancel works',voice('Cancel',token))
    check('cancelled result rejected',not voice('Commit',token,'错误'))
    other.close_sync(None)
    yield 100

iterator=sequence();success=False
def step():
    global success
    try:delay=next(iterator)
    except StopIteration:success=True;Gtk.main_quit();return False
    except Exception:
        import traceback;traceback.print_exc();Gtk.main_quit();return False
    GLib.timeout_add(delay,step);return False
try:
    GLib.timeout_add(100,step);Gtk.main()
finally:
    window.destroy();x.XCloseDisplay(display)
    for process in [core,broker]:
        process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    log.close();temporary.cleanup()
    (STATE/'integration-fcitx.json').write_text(json.dumps({'passed':success,
        'engine':'fixture' if args.mock_engine else 'official','checks':results},ensure_ascii=False,indent=2)+'\n')
raise SystemExit(0 if success else 1)
