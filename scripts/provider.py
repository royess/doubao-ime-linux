#!/usr/bin/env python3
"""Run an explicitly configured external adapter; no bundled vendor code."""
import importlib.util
import os
import socket
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from runtime import STATE, OPTIONS


def ipv4_connector(connect, enabled=False):
    """Optionally restrict the Doubao websocket host in this subprocess."""
    if not enabled:
        return connect
    def create_connection(address, *args, **kwargs):
        host, port = address
        if host == 'frontier-audio-ime-ws.doubao.com':
            addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            last_error = None
            for _, _, _, _, resolved in addresses:
                try:
                    return connect(resolved, *args, **kwargs)
                except OSError as error:
                    last_error = error
            if last_error:
                raise last_error
            raise OSError('No IPv4 address for Doubao voice endpoint')
        return connect(address, *args, **kwargs)
    return create_connection


def main():
    os.umask(0o077)
    name = os.environ.get('DOUBAO_ASR_ENTRY', OPTIONS.get('asr_entry'))
    if not name or not Path(name).is_file():
        raise RuntimeError('Set asr_entry to an external vinput-registry Doubao streaming entry.py; see docs/voice.md')
    private = STATE / 'private'
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ.setdefault('VINPUT_ASR_CREDENTIAL_PATH', str(private / 'credentials.json'))
    os.environ.setdefault('VINPUT_ASR_TIMEOUT', '15')
    os.environ.setdefault('VINPUT_ASR_FINISH_GRACE_SECS', '4')
    # Respect the user's proxy by default. Direct routing is an explicit option.
    direct = os.environ.get('DOUBAO_ASR_NO_PROXY', OPTIONS.get('asr_no_proxy', ''))
    if direct:
        for key in ('NO_PROXY', 'no_proxy'):
            os.environ[key] = ','.join(filter(None, (os.environ.get(key), direct)))
    spec = importlib.util.spec_from_file_location('doubao_upstream', Path(name).resolve())
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for attribute in ('ensure_healthy_credentials', 'ensure_credentials',
                      '_invalidate_credentials_after_route_failure', 'main'):
        if not hasattr(module, attribute):
            raise RuntimeError('Incompatible adapter; use the documented revision')
    module.ensure_healthy_credentials = module.ensure_credentials
    module._invalidate_credentials_after_route_failure = lambda state: None
    module.socket.create_connection = ipv4_connector(
        socket.create_connection, enabled=OPTIONS.get('asr_ipv4_only', False))
    return module.main()


if __name__ == '__main__':
    raise SystemExit(main())
