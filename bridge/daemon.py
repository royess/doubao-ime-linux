#!/usr/bin/env python3
import argparse
import json
import os
import signal
import subprocess
import time
from gi.repository import Gio, GLib
from audio import Session

NAME = 'org.doubaoime.Voice1'
PATH = '/org/doubaoime/Voice'
FCITX_PATH = '/org/fcitx/Fcitx5/DoubaoDictation'
FCITX_IFACE = 'org.fcitx.Fcitx5.DoubaoDictation1'
XML = '<node><interface name="'+NAME+'"><method name="Command"><arg type="s" direction="in"/>' \
      '<arg type="s" direction="out"/></method><method name="Status"><arg type="s" direction="out"/>' \
      '</method></interface></node>'


class Bridge:
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = self.bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'RequestName', GLib.Variant('(su)', (NAME, 4)), None,
            Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        if result != 1:
            raise RuntimeError('Doubao voice is already running')
        self.phase, self.token, self.session, self.last = 'idle', None, None, None
        self.generation, self.since = 0, time.monotonic()
        self.hold_generation = None
        self.loop = GLib.MainLoop()
        self.bus.register_object(PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], self.method)
        self.bus.signal_subscribe('org.fcitx.Fcitx5', FCITX_IFACE, 'Invalidated', FCITX_PATH,
            None, Gio.DBusSignalFlags.NONE, self.invalidated)
        self.bus.signal_subscribe('org.fcitx.Fcitx5', FCITX_IFACE, 'Shortcut', FCITX_PATH,
            None, Gio.DBusSignalFlags.NONE, self.shortcut)
        GLib.timeout_add(250, self.tick)

    def notify(self, text):
        if not self.quiet:
            subprocess.Popen(['notify-send', '-a', '豆包语音', '-r', '19224', '-t', '2500', '豆包语音', text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def fcitx(self, method, *args):
        return self.bus.call_sync('org.fcitx.Fcitx5', FCITX_PATH, FCITX_IFACE, method,
            GLib.Variant('('+'s'*len(args)+')', args) if args else None, None,
            Gio.DBusCallFlags.NONE, 1500, None).unpack()[0]

    def status(self):
        return {'phase': self.phase, 'generation': self.generation, 'last': self.last}

    def method(self, connection, sender, path, interface, method, parameters, invocation):
        try:
            if method == 'Command':
                self.command(parameters.unpack()[0])
            elif method != 'Status':
                raise ValueError('Unknown method')
            invocation.return_value(GLib.Variant('(s)', (json.dumps(self.status()),)))
        except Exception as error:
            invocation.return_dbus_error(NAME+'.Error', str(error))
            self.notify(str(error))

    def shortcut(self, connection, sender, path, interface, signal_name, parameters):
        action, context = parameters.unpack()
        print(json.dumps({'event': 'shortcut', 'action': action, 'phase': self.phase}), flush=True)
        try:
            if action == 'hold-start' and self.phase == 'idle':
                self.command('start', context)
                self.hold_generation = self.generation
            elif action in ('hold-stop', 'hold-cancel'):
                if self.hold_generation == self.generation:
                    self.hold_generation = None
                    self.command('stop' if action == 'hold-stop' else 'cancel')
            elif action == 'toggle':
                if self.hold_generation == self.generation and self.phase in ('connecting', 'recording'):
                    # Space while holding Alt changes this recording to hands-free.
                    self.hold_generation = None
                    self.notify('持续录音中；右 Alt + 空格结束，Esc 取消')
                else:
                    self.command('start' if self.phase == 'idle' else 'stop', context)
        except (GLib.Error, RuntimeError) as error:
            self.notify(str(error))

    def command(self, command, context=None):
        if command == 'toggle':
            command = 'start' if self.phase == 'idle' else 'stop'
        if command == 'start':
            if self.phase != 'idle':
                raise RuntimeError('当前听写尚未结束')
            token = self.fcitx('BeginForContext', context) if context else self.fcitx('Begin')
            if not token:
                raise RuntimeError('请先聚焦支持 Fcitx 的普通文本输入框')
            self.token = token
            self.generation += 1
            self.hold_generation = None
            generation = self.generation
            self.phase, self.since = 'connecting', time.monotonic()
            self.session = Session(lambda kind, payload: GLib.idle_add(self.event, generation, kind, payload),
                                   os.getenv('DOUBAO_AUDIO_SOURCE'))
            self.session.start()
            self.notify('正在连接…')
        elif command == 'stop':
            if self.phase in ('connecting', 'recording'):
                self.phase, self.since = 'processing', time.monotonic()
                self.session.stop.set()
                self.notify('正在识别…请勿打字或切换输入框，等待“已输入”提示')
        elif command == 'cancel':
            self.cancel('cancelled')
        else:
            raise ValueError('Unknown command')

    def cancel(self, reason):
        self.hold_generation = None
        if not self.session:
            return
        token, self.token = self.token, None
        if token:
            try:
                self.fcitx('Cancel', token)
            except GLib.Error:
                pass
        self.last = {'generation': self.generation, 'outcome': reason}
        print(json.dumps({'event': 'cancel', **self.last}), flush=True)
        if reason == 'fcitx-invalidated:typing':
            self.notify('听写已取消：识别完成前按了其他键；请等“已输入”后再打字')
        elif reason.startswith('fcitx-invalidated:') or reason == 'focus-or-key-cancelled':
            self.notify('听写已取消：输入框状态或焦点发生变化')
        self.phase, self.since = 'cancelling', time.monotonic()
        self.session.cancel.set()

    def invalidated(self, connection, sender, path, interface, signal_name, parameters):
        token, reason = parameters.unpack()
        if token == self.token:
            self.cancel('fcitx-invalidated:' + reason)

    def event(self, generation, kind, payload):
        if generation != self.generation or not self.session:
            return False
        if kind == 'recording' and self.phase == 'connecting':
            self.phase, self.since = 'recording', time.monotonic()
            self.notify('可以说话了；松开右 Alt 或再按右 Alt + 空格结束，Esc 取消'
                        if self.hold_generation == generation else
                        '可以说话了，再按快捷键结束；Esc 取消')
        elif kind == 'done':
            text = payload.get('text')
            outcome = 'no-final-result'
            if self.phase == 'processing' and self.token and text:
                try:
                    outcome = 'committed' if self.fcitx('Commit', self.token, text) else 'focus-cancelled'
                except GLib.Error:
                    outcome = 'fcitx-unavailable'
            elif payload.get('error'):
                outcome = payload['error']
            if self.token:
                try:
                    self.fcitx('Cancel', self.token)
                except GLib.Error:
                    pass
            if self.phase != 'cancelling':
                self.last = {'generation': generation, 'outcome': outcome,
                             'characters': len(text or '') if outcome == 'committed' else 0}
                self.last.update({key: payload[key] for key in
                    ('audio_seconds', 'peak', 'provider_events', 'error_category', 'provider_exit')
                    if key in payload})
                print(json.dumps({'event': 'done', **self.last}), flush=True)
                self.notify('已输入' if outcome == 'committed' else '本次未输入文字：'+outcome)
            self.session, self.token, self.phase = None, None, 'idle'
        return False

    def tick(self):
        if self.token:
            try:
                valid = self.fcitx('Valid', self.token)
            except GLib.Error:
                valid = False
            if not valid:
                self.cancel('focus-or-key-cancelled')
        limit = {'connecting': 25, 'recording': 120, 'processing': 20}.get(self.phase)
        if limit and time.monotonic()-self.since > limit:
            if self.phase == 'recording':
                self.command('stop')
            else:
                self.cancel(self.phase+'-timeout')
        return True

    def shutdown(self):
        self.cancel('shutdown')
        # Give the recording thread time to reap only its own children.
        def finish():
            if self.session:
                return True
            self.loop.quit()
            return False
        GLib.timeout_add(100, finish)
        GLib.timeout_add_seconds(5, lambda: self.loop.quit() or False)
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    bridge = Bridge(parser.parse_args().quiet)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, bridge.shutdown)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, bridge.shutdown)
    bridge.loop.run()
