import http.client
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from controller import Bridge
from lifecycle import Attempt, Cancelled


class AccessTests(unittest.TestCase):
    def client(self, status=204, error=None):
        client = Mock()
        client.getresponse.return_value.status = status
        if error:
            client.request.side_effect = error
        return client

    def test_fallback_uses_https_proxy_tunnel(self):
        first, second = self.client(error=TimeoutError()), self.client()
        with patch('controller.http.client.HTTPSConnection', side_effect=[first, second]) as constructor:
            attempt = Attempt()
            Bridge._check_access(1234, attempt)
        first.set_tunnel.assert_called_once_with('www.gstatic.com',443)
        second.set_tunnel.assert_called_once_with('cp.cloudflare.com',443)
        for call in constructor.call_args_list:
            self.assertEqual(call.args, ('127.0.0.1',1234))
            self.assertEqual(call.kwargs['timeout'],8)
        first.close.assert_called_once()
        second.close.assert_called_once()
        self.assertIsNone(attempt.client)

    def test_failed_endpoints_report_categories(self):
        with patch('controller.http.client.HTTPSConnection', side_effect=[self.client(error=TimeoutError()), self.client(502)]):
            with self.assertRaisesRegex(ValueError, 'TIMEOUT, HTTP_502'):
                Bridge._check_access(1234,Attempt())

    def test_cancel_does_not_try_fallback(self):
        attempt=Attempt()
        client=self.client()
        def cancel(*args,**kwargs):
            attempt.event.set()
            raise OSError('cancelled socket')
        client.request.side_effect=cancel
        with patch('controller.http.client.HTTPSConnection',return_value=client) as constructor:
            with self.assertRaises(Cancelled):
                Bridge._check_access(1234,attempt)
        self.assertEqual(constructor.call_count,1)
        client.close.assert_called_once()


class StateTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.connection=Mock(port=1234)
        self.api=Bridge(self.directory.name,connect=Mock(return_value=self.connection))
        self.api._nodes={'server':{}}
        self.api._check_access=Mock(side_effect=ValueError('test failure'))

    def tearDown(self):
        self.api._close_window()
        self.api._wake.set()
        self.api._monitor.join(timeout=2)
        self.api._store.db.close()
        self.directory.cleanup()

    def settle(self):
        deadline=time.monotonic()+2
        while self.api._attempt and time.monotonic()<deadline:
            time.sleep(.01)
        self.assertIsNone(self.api._attempt)

    def test_manual_failure_is_terminal_and_restores_connection(self):
        self.api.connect('server')
        self.settle()
        state=self.api.snapshot()
        self.assertFalse(state['connecting'])
        self.assertFalse(state['reconnecting'])
        self.assertFalse(state['active'])
        self.assertEqual(state['error'],'test failure')
        self.connection.close.assert_called_once()

    def test_automatic_failures_stop_after_three(self):
        for count in range(3):
            self.api.connect('server',automatic=True)
            self.settle()
            state=self.api.snapshot()
            self.assertEqual(state['reconnecting'],count<2)
        self.assertEqual(self.connection.close.call_count,3)


if __name__=='__main__': unittest.main()
