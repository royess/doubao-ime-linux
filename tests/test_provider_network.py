import importlib.util
from pathlib import Path
import socket
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('provider_network',Path(__file__).resolve().parents[1]/'scripts/provider.py')
provider=importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)

class Network(unittest.TestCase):
    def test_default_and_explicit_false_preserve_system_address_selection(self):
        connect=Mock()
        self.assertIs(provider.ipv4_connector(connect),connect)
        self.assertIs(provider.ipv4_connector(connect,enabled=False),connect)

    def test_only_doubao_host_uses_ipv4_and_preserves_options(self):
        connect=Mock(return_value='connected')
        wrapped=provider.ipv4_connector(connect,enabled=True)
        addresses=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('192.0.2.1',443))]
        with patch.object(provider.socket,'getaddrinfo',return_value=addresses) as resolve:
            self.assertEqual(wrapped(('frontier-audio-ime-ws.doubao.com',443),timeout=15),'connected')
            resolve.assert_called_once_with('frontier-audio-ime-ws.doubao.com',443,socket.AF_INET,socket.SOCK_STREAM)
            connect.assert_called_once_with(('192.0.2.1',443),timeout=15)
            resolve.reset_mock()
            wrapped(('example.org',443),timeout=2)
            resolve.assert_not_called()
            connect.assert_called_with(('example.org',443),timeout=2)

    def test_next_ipv4_address_is_tried_after_failure(self):
        connect=Mock(side_effect=[TimeoutError(),'connected'])
        addresses=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in ('192.0.2.1','192.0.2.2')]
        with patch.object(provider.socket,'getaddrinfo',return_value=addresses):
            self.assertEqual(provider.ipv4_connector(connect,enabled=True)(('frontier-audio-ime-ws.doubao.com',443),timeout=2),'connected')
        self.assertEqual(connect.call_count,2)

if __name__=='__main__':unittest.main()
