#!/usr/bin/env python3
import argparse
from gi.repository import Gio, GLib

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['start', 'stop', 'toggle', 'cancel', 'status'], nargs='?', default='status')
args = parser.parse_args()
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
try:
    result = bus.call_sync('org.doubaoime.Voice1', '/org/doubaoime/Voice', 'org.doubaoime.Voice1',
        'Status' if args.command == 'status' else 'Command',
        None if args.command == 'status' else GLib.Variant('(s)', (args.command,)), None,
        Gio.DBusCallFlags.NONE, 5000, None)
    print(result.unpack()[0])
except GLib.Error as error:
    parser.exit(1, str(error)+'\n')
